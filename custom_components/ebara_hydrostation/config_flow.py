"""Config flow for Ebara Hydrostation integration."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_GATEWAY_DEVICE_NAME,
    CONF_GATEWAY_ENTRY_ID,
    CONF_GATEWAY_HOST,
    CONF_GATEWAY_NOISE_PSK,
    CONF_GATEWAY_PORT,
    CONF_HYDRO_MAC,
    CONF_HYDRO_NAME,
    DOMAIN,
    ESP_ENTITY_DISCOVERED,
    ESP_ENTITY_GW_STATUS,
    ESP_ENTITY_TARGET_MAC,
)

_LOGGER = logging.getLogger(__name__)

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

# Entities this component always creates on the ESP32 gateway, used to
# recognize a gateway regardless of what the user named the device itself.
_GATEWAY_SIGNATURE_ENTITY_NAMES = {ESP_ENTITY_TARGET_MAC, ESP_ENTITY_GW_STATUS}


class EbaraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ebara Hydrostation."""

    VERSION = 1

    def __init__(self) -> None:
        self._gateway_host: str = ""
        self._gateway_port: int = 6053
        self._gateway_noise_psk: str | None = None
        self._gateway_entry_id: str | None = None  # native ESPHome config entry
        self._gateway_device_name: str | None = None
        self._discovered_hydros: dict[str, str] = {}  # mac -> list label
        self._hydro_names: dict[str, str] = {}  # mac -> pump name (e.g. HYDRO_1234)
        # key: "host:port" → {"label", "noise_psk", "entry_id", "device_name"}
        self._gateway_options: dict[str, dict[str, Any]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._gateway_options = self._find_esphome_gateways()
        if self._gateway_options:
            return await self.async_step_gateway()
        return await self.async_step_manual_gateway()

    async def async_step_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            selected = user_input["gateway"]
            gw = self._gateway_options.get(selected, {})
            host, _, port_str = selected.partition(":")
            self._set_gateway(
                host,
                int(port_str) if port_str else 6053,
                gw.get("entry_id"),
                gw.get("noise_psk"),
                gw.get("device_name"),
            )
            if self._gateway_in_use():
                return self.async_abort(reason="gateway_already_configured")
            return await self.async_step_select_hydro()
        schema = vol.Schema(
            {
                vol.Required("gateway"): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": k, "label": v["label"]}
                            for k, v in self._gateway_options.items()
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="gateway", data_schema=schema)

    async def async_step_manual_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input["host"].strip()
            # The gateway must already be set up in the native ESPHome
            # integration: discovery list and target MAC are read/written
            # through its entities.
            esphome_entry = next(
                (
                    e
                    for e in self.hass.config_entries.async_entries("esphome")
                    if e.data.get("host") == host
                ),
                None,
            )
            if esphome_entry is None:
                errors["base"] = "esphome_entry_missing"
            else:
                self._set_gateway(
                    host,
                    int(user_input.get("port", 6053)),
                    esphome_entry.entry_id,
                    esphome_entry.data.get("noise_psk"),
                    esphome_entry.data.get("device_name"),
                )
                if self._gateway_in_use():
                    return self.async_abort(reason="gateway_already_configured")
                return await self.async_step_select_hydro()
        schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("port", default=6053): int,
            }
        )
        return self.async_show_form(
            step_id="manual_gateway", data_schema=schema, errors=errors
        )

    async def async_step_select_hydro(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None and user_input.get("hydro_mac"):
            mac = user_input["hydro_mac"]
            # Abort before touching the gateway if this pump already exists.
            await self.async_set_unique_id(mac.replace(":", "").lower())
            self._abort_if_unique_id_configured()
            # Device/entry name: the pump's own name, not the list label
            # (which also carries MAC and RSSI).
            name = self._hydro_names.get(mac, "Hydrostation")
            await self._write_target_mac(mac)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_GATEWAY_HOST: self._gateway_host,
                    CONF_GATEWAY_PORT: self._gateway_port,
                    CONF_GATEWAY_NOISE_PSK: self._gateway_noise_psk,
                    CONF_GATEWAY_DEVICE_NAME: self._gateway_device_name,
                    CONF_GATEWAY_ENTRY_ID: self._gateway_entry_id,
                    CONF_HYDRO_MAC: mac,
                    CONF_HYDRO_NAME: name,
                },
            )
        # First display, or the error form below was submitted (retry).
        self._discovered_hydros = self._read_discovered_hydros()
        if not self._discovered_hydros:
            errors["base"] = "no_devices_found"
            return self.async_show_form(
                step_id="select_hydro", data_schema=vol.Schema({}), errors=errors
            )
        schema = vol.Schema(
            {
                vol.Required("hydro_mac"): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": mac, "label": label}
                            for mac, label in self._discovered_hydros.items()
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="select_hydro", data_schema=schema)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_gateway(
        self,
        host: str,
        port: int,
        entry_id: str | None,
        noise_psk: str | None,
        device_name: str | None,
    ) -> None:
        self._gateway_host = host
        self._gateway_port = port
        self._gateway_entry_id = entry_id
        self._gateway_noise_psk = noise_psk
        self._gateway_device_name = device_name

    def _gateway_in_use(self) -> bool:
        """One gateway drives exactly one pump (single BLE target)."""
        return any(
            entry.data.get(CONF_GATEWAY_HOST) == self._gateway_host
            or (
                self._gateway_entry_id is not None
                and entry.data.get(CONF_GATEWAY_ENTRY_ID) == self._gateway_entry_id
            )
            for entry in self._async_current_entries(include_ignore=False)
        )

    def _gateway_entity_id(self, original_name: str) -> str | None:
        """entity_id of a gateway entity, by the name the component gives it
        (not by entity_id, which the user may have renamed)."""
        if self._gateway_entry_id is None:
            return None
        ent_reg = er.async_get(self.hass)
        for entity in er.async_entries_for_config_entry(ent_reg, self._gateway_entry_id):
            if entity.original_name == original_name:
                return entity.entity_id
        return None

    def _find_esphome_gateways(self) -> dict[str, dict[str, Any]]:
        """ESPHome config entries that look like an Ebara Hydrostation gateway.

        Matched by this component's own signature entities rather than the
        device name, which is fully user-customizable.
        """
        ent_reg = er.async_get(self.hass)
        gateways: dict[str, dict[str, Any]] = {}
        for entry in self.hass.config_entries.async_entries("esphome"):
            names = {
                e.original_name for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
            }
            if not _GATEWAY_SIGNATURE_ENTITY_NAMES.issubset(names):
                continue
            host = entry.data.get("host", "")
            if not host:
                continue
            port = entry.data.get("port", 6053)
            gateways[f"{host}:{port}"] = {
                "label": entry.data.get("device_name") or entry.title or host,
                "noise_psk": entry.data.get("noise_psk"),
                "entry_id": entry.entry_id,
                "device_name": entry.data.get("device_name"),
            }
        return gateways

    def _read_discovered_hydros(self) -> dict[str, str]:
        """Pumps seen by the gateway, from the HA state machine."""
        result: dict[str, str] = {}

        discovered_entity_id = self._gateway_entity_id(ESP_ENTITY_DISCOVERED)
        if discovered_entity_id is None:
            _LOGGER.warning(
                "'%s' entity not found for gateway entry %s",
                ESP_ENTITY_DISCOVERED,
                self._gateway_entry_id,
            )
        else:
            state = self.hass.states.get(discovered_entity_id)
            if state and state.state not in ("", "unavailable", "unknown"):
                try:
                    devices = json.loads(state.state)
                except json.JSONDecodeError as err:
                    _LOGGER.error("Invalid discovered-devices JSON from the gateway: %s", err)
                    devices = []
                for d in devices if isinstance(devices, list) else []:
                    mac = str(d.get("mac", ""))
                    name = str(d.get("name", mac))
                    if not _MAC_RE.match(mac):
                        continue
                    # Only HYDRO pumps are supported; the gateway flags other
                    # families (e.g. HYSTA) with "supported": false.
                    if not d.get("supported", True):
                        _LOGGER.warning("Ignoring %s (%s): pump family not supported", name, mac)
                        continue
                    result[mac] = f"{name} ({mac}, {d.get('rssi', 0)} dBm)"
                    self._hydro_names[mac] = name

        # A gateway already paired with a pump does not scan: offer its
        # current target MAC as well, so re-associating it stays possible.
        target_mac_entity_id = self._gateway_entity_id(ESP_ENTITY_TARGET_MAC)
        if target_mac_entity_id:
            state = self.hass.states.get(target_mac_entity_id)
            if state and _MAC_RE.match(state.state) and state.state not in result:
                mac = state.state
                result[mac] = f"Hydrostation ({mac})"
                self._hydro_names.setdefault(mac, "Hydrostation")

        return result

    async def _write_target_mac(self, mac: str) -> None:
        """Write the target MAC to the gateway via its native text entity.

        Not fatal: the coordinator also sends it at every (re)connection.
        """
        target_entity_id = self._gateway_entity_id(ESP_ENTITY_TARGET_MAC)
        if target_entity_id is None:
            _LOGGER.warning("Target MAC entity not found for gateway %s", self._gateway_entry_id)
            return
        try:
            await self.hass.services.async_call(
                "text",
                "set_value",
                {"entity_id": target_entity_id, "value": mac},
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001 — retried by the coordinator
            _LOGGER.warning("Could not write target MAC to the gateway: %s", err)
            return
        _LOGGER.info("Wrote target MAC %s to %s", mac, target_entity_id)
