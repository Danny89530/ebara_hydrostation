"""Coordinator for Ebara Hydrostation: maintains persistent aioesphomeapi connection."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aioesphomeapi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_GATEWAY_HOST,
    CONF_GATEWAY_NOISE_PSK,
    CONF_GATEWAY_PORT,
    CONF_HYDRO_MAC,
    DOMAIN,
    ESP_ENTITY_TARGET_MAC,
)

_LOGGER = logging.getLogger(__name__)

# Reconnect delay (seconds)
RECONNECT_DELAY = 30


class EbaraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages a persistent aioesphomeapi connection to the ESP32 gateway.

    Entity state changes pushed by ESPHome are forwarded to all registered
    HA entities via DataUpdateCoordinator.async_set_updated_data().
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # push-based
        )
        self.entry = entry
        self.host: str = entry.data[CONF_GATEWAY_HOST]
        self.port: int = entry.data.get(CONF_GATEWAY_PORT, 6053)
        self.noise_psk: str | None = entry.data.get(CONF_GATEWAY_NOISE_PSK)
        self.hydro_mac: str | None = entry.data.get(CONF_HYDRO_MAC)

        self._client: aioesphomeapi.APIClient | None = None
        self._entity_key_map: dict[str, int] = {}   # entity_name → numeric key
        self._current_data: dict[str, Any] = {}
        self._reconnect_task: asyncio.Task | None = None
        self._unsub_states: Any = None
        self._connected: bool = False
        self._shutting_down: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    async def async_start(self) -> None:
        """Connect to the ESP32 gateway (called from async_setup_entry)."""
        await self._connect()
        if not self._connected:
            self._schedule_reconnect()

    async def async_stop(self) -> None:
        """Disconnect and cancel any reconnect task."""
        self._shutting_down = True
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self._disconnect()

    def get_value(self, entity_name: str) -> Any:
        """Return the latest cached value for a named ESP32 entity."""
        return self._current_data.get(entity_name)

    async def async_send_command(self, entity_name: str, value: Any) -> None:
        """Send a command to a writable ESP32 entity.

        Dispatches to the correct API call based on value type.
        """
        if not self._client or not self._connected:
            raise RuntimeError("Not connected to ESP32 gateway")
        key = self._entity_key_map.get(entity_name)
        if key is None:
            raise ValueError(f"Entity '{entity_name}' not found on ESP32 (map has {list(self._entity_key_map)})")

        # aioesphomeapi's *_command methods are synchronous (they fire over
        # the existing connection without awaiting a response) — not coroutines.
        if isinstance(value, bool):
            self._client.switch_command(key, value)
        elif isinstance(value, (int, float)):
            self._client.number_command(key, float(value))
        elif isinstance(value, str):
            self._client.text_command(key, value)
        else:
            raise TypeError(f"Unsupported command value type: {type(value)}")

    # ── Connection management ─────────────────────────────────────────────────

    async def _connect(self) -> None:
        """Establish connection to ESP32 and subscribe to states."""
        _LOGGER.debug("Connecting to ESP32 gateway at %s:%d", self.host, self.port)
        self._client = aioesphomeapi.APIClient(
            self.host,
            self.port,
            password=None,
            noise_psk=self.noise_psk,
        )
        try:
            await self._client.connect(login=True)
            self._connected = True

            entities, _ = await self._client.list_entities_services()
            self._entity_key_map = {}
            for e in entities:
                name = getattr(e, "name", None)
                key = getattr(e, "key", None)
                if name and key is not None:
                    self._entity_key_map[name] = key

            _LOGGER.info(
                "Connected to ESP32 gateway %s. Found %d entities: %s",
                self.host,
                len(self._entity_key_map),
                list(self._entity_key_map.keys()),
            )

            # Subscribe to all state updates (push)
            self._unsub_states = self._client.subscribe_states(self._on_state_change)

            # Register disconnect callback
            self._client.on_stop = self._on_disconnect

            # Re-send target MAC so ESP32 knows which Hydro to connect to
            # (critical after ESP32 reboot/NVS erase)
            if self.hydro_mac:
                mac_key = self._entity_key_map.get(ESP_ENTITY_TARGET_MAC)
                if mac_key is not None:
                    try:
                        self._client.text_command(mac_key, self.hydro_mac)
                        _LOGGER.info("Sent target MAC %s to ESP32 gateway", self.hydro_mac)
                    except Exception as err:
                        _LOGGER.warning("Failed to send target MAC to ESP32: %s", err)
                else:
                    _LOGGER.warning(
                        "ESP32 entity '%s' not found in map — cannot send MAC",
                        ESP_ENTITY_TARGET_MAC,
                    )

        except Exception as err:
            _LOGGER.error("Failed to connect to ESP32 gateway %s: %s", self.host, err)
            self._connected = False
            # Retry scheduling is the caller's responsibility (async_start()
            # or _reconnect_loop() below) — this method must stay free of
            # scheduling side effects, since it's also invoked from inside
            # the reconnect loop's own task on every retry.

    async def _disconnect(self) -> None:
        """Cleanly disconnect from the ESP32."""
        self._connected = False
        if self._unsub_states:
            try:
                self._unsub_states()
            except Exception:
                pass
            self._unsub_states = None
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    def _on_disconnect(self) -> None:
        """Called by aioesphomeapi when the connection drops."""
        self._connected = False
        if self._shutting_down:
            # Our own async_stop()/_disconnect() may trigger this callback for
            # an intentional disconnect (entry unload/reload) — without this
            # guard a reconnect would get scheduled 30s after the coordinator
            # was supposedly torn down.
            return
        _LOGGER.warning("ESP32 gateway disconnected, scheduling reconnect")
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Ensure a reconnect-retry loop is running."""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Retry the connection every RECONNECT_DELAY seconds, in a single
        long-lived task, until it succeeds or the coordinator is shut down.

        A chain of self-rescheduling one-shot tasks doesn't work here: a
        failed retry runs *inside* this same task, so a done-check guard
        in _schedule_reconnect() would see itself as still running and
        silently skip scheduling any further attempt — permanently ending
        the retry loop after exactly one failure.
        """
        while not self._shutting_down and not self._connected:
            await asyncio.sleep(RECONNECT_DELAY)
            if self._shutting_down or self._connected:
                return
            await self._connect()

    # ── State handling ────────────────────────────────────────────────────────

    @callback
    def _on_state_change(self, state: Any) -> None:
        """Called whenever any ESP32 entity state changes."""
        key = getattr(state, "key", None)
        if key is None:
            return

        # Resolve entity name from key
        entity_name: str | None = None
        for name, k in self._entity_key_map.items():
            if k == key:
                entity_name = name
                break
        if entity_name is None:
            return

        # Extract value - handle all aioesphomeapi state types
        value = getattr(state, "state", None)
        missing = getattr(state, "missing_state", False)
        if missing:
            value = None

        if value is not None:
            self._current_data[entity_name] = value
            _LOGGER.debug("State update: '%s' = %r", entity_name, value)

        # Notify all HA entities (triggers async_write_ha_state on each)
        self.async_set_updated_data(dict(self._current_data))
