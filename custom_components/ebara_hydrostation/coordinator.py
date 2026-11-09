"""Coordinator for Ebara Hydrostation: persistent aioesphomeapi connection."""
from __future__ import annotations

import logging
from typing import Any

import aioesphomeapi
from aioesphomeapi.reconnect_logic import ReconnectLogic

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_GATEWAY_DEVICE_NAME,
    CONF_GATEWAY_HOST,
    CONF_GATEWAY_NOISE_PSK,
    CONF_GATEWAY_PORT,
    CONF_HYDRO_MAC,
    DOMAIN,
    ESP_ENTITY_TARGET_MAC,
    GATEWAY_CHANGELOG_URL,
    GATEWAY_V2_ENTITIES,
)

_LOGGER = logging.getLogger(__name__)

_CLIENT_INFO = "Home Assistant Ebara Hydrostation"


class EbaraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages a persistent aioesphomeapi connection to the ESP32 gateway.

    Connection lifecycle (connect, retry with backoff, detection of a lost
    connection) is delegated to aioesphomeapi's ReconnectLogic, the same class
    Home Assistant's native ESPHome integration uses. When the gateway's mDNS
    name is known, ReconnectLogic also follows it if its IP address changes.

    Entity states pushed by ESPHome are forwarded to all HA entities via
    DataUpdateCoordinator.async_set_updated_data() (no polling).
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,  # push-based
        )
        self.host: str = entry.data[CONF_GATEWAY_HOST]
        self.port: int = entry.data.get(CONF_GATEWAY_PORT, 6053)
        self.noise_psk: str | None = entry.data.get(CONF_GATEWAY_NOISE_PSK)
        self.hydro_mac: str | None = entry.data.get(CONF_HYDRO_MAC)
        self.device_name: str | None = entry.data.get(CONF_GATEWAY_DEVICE_NAME)

        self._client: aioesphomeapi.APIClient | None = None
        self._reconnect_logic: ReconnectLogic | None = None
        self._name_to_key: dict[str, int] = {}
        self._key_to_name: dict[int, str] = {}
        self._current_data: dict[str, Any] = {}
        self._unsub_states: Any = None
        self._connected: bool = False
        self.data = {}

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        """True while the API connection to the gateway is established."""
        return self._connected

    async def async_start(self) -> None:
        """Start connecting to the ESP32 gateway (called from async_setup_entry)."""
        zeroconf_instance = await zeroconf.async_get_async_instance(self.hass)
        self._client = aioesphomeapi.APIClient(
            self.host,
            self.port,
            None,  # API password: deprecated in ESPHome, encryption (noise) is used
            client_info=_CLIENT_INFO,
            zeroconf_instance=zeroconf_instance,
            noise_psk=self.noise_psk,
            # Refuse to talk to a different ESPHome device that took over the
            # same IP address (DHCP reassignment).
            expected_name=self.device_name,
        )
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
        self._unsubscribe_states()
        if self._client is not None:
            try:
                await self._client.disconnect()
            except aioesphomeapi.APIConnectionError:
                pass
        self._connected = False

    def get_value(self, entity_name: str) -> Any:
        """Return the latest value of a named gateway entity (None = unknown)."""
        return self._current_data.get(entity_name)

    async def async_send_command(self, entity_name: str, value: Any) -> None:
        """Send a command to a writable gateway entity."""
        if self._client is None or not self._connected:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_not_connected"
            )
        key = self._name_to_key.get(entity_name)
        if key is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="gateway_entity_missing",
                translation_placeholders={"entity": entity_name},
            )
        # The *_command methods are synchronous: they are written to the
        # existing connection without waiting for a response.
        if isinstance(value, bool):
            self._client.switch_command(key, value)
        elif isinstance(value, (int, float)):
            self._client.number_command(key, float(value))
        elif isinstance(value, str):
            self._client.text_command(key, value)
        else:
            raise TypeError(f"Unsupported command value type: {type(value)}")

    async def _async_update_data(self) -> dict[str, Any]:
        """Push-based: a manual refresh just returns the cached states."""
        return dict(self._current_data)

    # ── Connection lifecycle (called by ReconnectLogic) ─────────────────────────

    async def _on_connect(self) -> None:
        """Called by ReconnectLogic once a connection and handshake succeed."""
        assert self._client is not None
        entities, _ = await self._client.list_entities_services()
        self._name_to_key = {}
        self._key_to_name = {}
        for e in entities:
            name = getattr(e, "name", None)
            key = getattr(e, "key", None)
            if name and key is not None:
                self._name_to_key[name] = key
                self._key_to_name[key] = name

        _LOGGER.info(
            "Connected to ESP32 gateway %s (%d entities)", self.host, len(self._name_to_key)
        )
        _LOGGER.debug("Gateway entities: %s", list(self._name_to_key))
        self._check_gateway_version()

        # The connection is new on every (re)connect: subscribe again. The
        # gateway sends the current state of every entity right away.
        self._current_data = {}
        self._unsub_states = self._client.subscribe_states(self._on_state_change)
        self._connected = True

        # Re-send the target MAC so the gateway knows which pump to use
        # (critical after an ESP32 NVS erase). Same MAC: no-op on the gateway.
        if self.hydro_mac:
            mac_key = self._name_to_key.get(ESP_ENTITY_TARGET_MAC)
            if mac_key is not None:
                self._client.text_command(mac_key, self.hydro_mac)
                _LOGGER.debug("Sent target MAC %s to the gateway", self.hydro_mac)
            else:
                _LOGGER.warning(
                    "Gateway entity '%s' not found — cannot send the target MAC",
                    ESP_ENTITY_TARGET_MAC,
                )

        self.async_set_updated_data(dict(self._current_data))

    async def _on_disconnect(self, expected_disconnect: bool) -> None:
        """Called by ReconnectLogic whenever the connection is lost."""
        self._connected = False
        self._unsubscribe_states()
        # Never show the last readings as if they were current.
        self._current_data = {}
        log = _LOGGER.debug if expected_disconnect else _LOGGER.warning
        log("ESP32 gateway %s disconnected (expected=%s) — reconnecting", self.host, expected_disconnect)
        self.async_set_updated_data({})

    async def _on_connect_error(self, err: Exception) -> None:
        """Called by ReconnectLogic when a connection attempt fails."""
        _LOGGER.debug("Failed to connect to ESP32 gateway %s: %s", self.host, err)

    @property
    def outdated_issue_id(self) -> str:
        return f"gateway_outdated_{self.config_entry.entry_id}"

    def _check_gateway_version(self) -> None:
        """Raise (or clear) a repair issue if the gateway lacks the entities
        of the current ESPHome component."""
        missing = [name for name in GATEWAY_V2_ENTITIES if name not in self._name_to_key]
        if not missing:
            ir.async_delete_issue(self.hass, DOMAIN, self.outdated_issue_id)
            return
        _LOGGER.warning(
            "ESP32 gateway %s does not expose %s: update the ESPHome component and its YAML",
            self.host,
            ", ".join(missing),
        )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self.outdated_issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="gateway_outdated",
            translation_placeholders={
                "gateway": self.device_name or self.host,
                "missing": ", ".join(missing),
            },
            learn_more_url=GATEWAY_CHANGELOG_URL,
        )

    def _unsubscribe_states(self) -> None:
        if self._unsub_states:
            try:
                self._unsub_states()
            except Exception:  # noqa: BLE001 — connection may already be gone
                pass
            self._unsub_states = None

    # ── State handling ────────────────────────────────────────────────────────

    @callback
    def _on_state_change(self, state: Any) -> None:
        """Called whenever a gateway entity state changes."""
        key = getattr(state, "key", None)
        entity_name = self._key_to_name.get(key) if key is not None else None
        if entity_name is None:
            return

        value = getattr(state, "state", None)
        if getattr(state, "missing_state", False):
            value = None

        if value is None or (isinstance(value, float) and value != value):  # missing or NaN
            # The gateway marks live values unknown when the pump is offline:
            # drop the cached value instead of keeping a stale reading.
            if self._current_data.pop(entity_name, None) is None:
                return
            _LOGGER.debug("State update: '%s' = unknown", entity_name)
        else:
            if self._current_data.get(entity_name) == value:
                return
            self._current_data[entity_name] = value
            _LOGGER.debug("State update: '%s' = %r", entity_name, value)

        self.async_set_updated_data(dict(self._current_data))
