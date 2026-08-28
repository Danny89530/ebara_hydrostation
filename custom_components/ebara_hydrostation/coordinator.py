"""Coordinator for Ebara Hydrostation: maintains persistent aioesphomeapi connection."""
from __future__ import annotations

import logging
from typing import Any

import aioesphomeapi
from aioesphomeapi.reconnect_logic import ReconnectLogic

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_GATEWAY_DEVICE_NAME,
    CONF_GATEWAY_HOST,
    CONF_GATEWAY_NOISE_PSK,
    CONF_GATEWAY_PORT,
    CONF_HYDRO_MAC,
    DOMAIN,
    ESP_ENTITY_TARGET_MAC,
)

_LOGGER = logging.getLogger(__name__)


class EbaraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages a persistent aioesphomeapi connection to the ESP32 gateway.

    Connection lifecycle (connect, retry with backoff, and detecting a lost
    connection) is delegated to aioesphomeapi's own ReconnectLogic, the same
    class Home Assistant's native ESPHome integration uses. When the
    gateway's mDNS name is known, ReconnectLogic also reconnects
    automatically if its IP address changes.

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
        self.device_name: str | None = entry.data.get(CONF_GATEWAY_DEVICE_NAME)

        self._client: aioesphomeapi.APIClient | None = None
        self._reconnect_logic: ReconnectLogic | None = None
        self._entity_key_map: dict[str, int] = {}   # entity_name → numeric key
        self._current_data: dict[str, Any] = {}
        self._unsub_states: Any = None
        self._connected: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    async def async_start(self) -> None:
        """Start connecting to the ESP32 gateway (called from async_setup_entry)."""
        self._client = aioesphomeapi.APIClient(
            self.host,
            self.port,
            password=None,
            noise_psk=self.noise_psk,
        )
        zeroconf_instance = await zeroconf.async_get_async_instance(self.hass)
        self._reconnect_logic = ReconnectLogic(
            client=self._client,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
            on_connect_error=self._on_connect_error,
            zeroconf_instance=zeroconf_instance,
            name=self.device_name or self.host,
        )
        await self._reconnect_logic.start()

    async def async_stop(self) -> None:
        """Stop the reconnect logic and disconnect from the ESP32."""
        if self._reconnect_logic is not None:
            await self._reconnect_logic.stop()
        if self._unsub_states:
            try:
                self._unsub_states()
            except Exception:
                pass
            self._unsub_states = None
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._connected = False

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

    # ── Connection lifecycle (called by ReconnectLogic) ─────────────────────────

    async def _on_connect(self) -> None:
        """Called by ReconnectLogic once a connection and handshake succeed."""
        assert self._client is not None
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

        # Subscribe to all state updates (push) — the underlying connection
        # is new on every (re)connect, so this must be re-subscribed each time.
        self._unsub_states = self._client.subscribe_states(self._on_state_change)
        self._connected = True

        # Re-send target MAC so ESP32 knows which Hydro to connect to
        # (critical after ESP32 reboot/NVS erase).
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

        # Notify entities immediately so `available` flips back to True and
        # any previously-cached values are re-displayed without waiting for
        # the next ESP-side poll response.
        self.async_set_updated_data(dict(self._current_data))

    async def _on_disconnect(self, expected_disconnect: bool) -> None:
        """Called by ReconnectLogic whenever the connection is lost."""
        self._connected = False
        if self._unsub_states:
            try:
                self._unsub_states()
            except Exception:
                pass
            self._unsub_states = None
        _LOGGER.warning(
            "ESP32 gateway %s disconnected (expected=%s) — reconnecting",
            self.host,
            expected_disconnect,
        )
        # Notify entities immediately so `available` flips to False right
        # away, instead of leaving stale data displayed as if still current.
        self.async_set_updated_data(dict(self._current_data))

    async def _on_connect_error(self, err: Exception) -> None:
        """Called by ReconnectLogic when a connection attempt itself fails."""
        _LOGGER.debug("Failed to connect to ESP32 gateway %s: %s", self.host, err)

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
