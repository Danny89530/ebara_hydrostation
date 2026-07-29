"""Config flow for Ebara Hydrostation integration."""
from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_GATEWAY_HOST,
    CONF_GATEWAY_NOISE_PSK,
    CONF_GATEWAY_PORT,
    CONF_HYDRO_MAC,
    CONF_HYDRO_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EbaraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ebara Hydrostation."""

    VERSION = 1

    def __init__(self) -> None:
        self._gateway_host: str = ""
        self._gateway_port: int = 6053
        self._gateway_noise_psk: str | None = None
        self._gateway_entry_id: str | None = None  # ESPHome config entry ID
        self._discovered_hydros: dict[str, str] = {}
        # key: "host:port", value: {"label": str, "noise_psk": str|None, "entry_id": str}
        self._gateway_options: dict[str, dict] = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of an Ebara gateway."""
        host = discovery_info.host
        port = discovery_info.port or 6053
        for entry in self._async_current_entries():
            if entry.data.get(CONF_GATEWAY_HOST) == host:
                return self.async_abort(reason="already_configured")
        self._gateway_host = host
        self._gateway_port = port
        self.context["title_placeholders"] = {"host": host}
        return await self.async_step_select_hydro()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._gateway_options = await self._find_esphome_gateways()
        if self._gateway_options:
            return await self.async_step_gateway()
        return await self.async_step_manual_gateway()

    async def async_step_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = user_input["gateway"]
            host, _, port_str = selected.partition(":")
            self._gateway_host = host
            self._gateway_port = int(port_str) if port_str else 6053
            gw = self._gateway_options.get(selected, {})
            self._gateway_noise_psk = gw.get("noise_psk")
            self._gateway_entry_id = gw.get("entry_id")
            return await self.async_step_select_hydro()
        if not self._gateway_options:
            return await self.async_step_manual_gateway()
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
        return self.async_show_form(step_id="gateway", data_schema=schema, errors=errors)

    async def async_step_manual_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._gateway_host = user_input["host"]
            self._gateway_port = int(user_input.get("port", 6053))
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
        if user_input is not None:
            mac = user_input["hydro_mac"]
            name = self._discovered_hydros.get(mac, mac)
            try:
                await self._write_target_mac(mac)
            except Exception as err:
                _LOGGER.warning("Could not write target MAC to ESP32: %s", err)
            unique_id = mac.replace(":", "").lower()
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=name,
                data={
                    CONF_GATEWAY_HOST: self._gateway_host,
                    CONF_GATEWAY_PORT: self._gateway_port,
                    CONF_GATEWAY_NOISE_PSK: self._gateway_noise_psk,
                    CONF_HYDRO_MAC: mac,
                    CONF_HYDRO_NAME: name,
                },
            )
        try:
            self._discovered_hydros = await self._read_discovered_hydros()
        except Exception as err:
            _LOGGER.error("Failed to read from ESP32 gateway: %s", err)
            errors["base"] = "cannot_connect"
        if not errors and not self._discovered_hydros:
            errors["base"] = "no_devices_found"
        if errors:
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
        return self.async_show_form(
            step_id="select_hydro", data_schema=schema, errors=errors
        )

    async def _find_esphome_gateways(self) -> dict[str, dict]:
        gateways: dict[str, dict] = {}
        for entry in self.hass.config_entries.async_entries("esphome"):
            device_name = (
                entry.data.get("device_name")
                or entry.data.get("name")
                or entry.title
                or ""
            )
            if device_name.startswith("ebara-hydro"):
                host = entry.data.get("host", "")
                port = entry.data.get("port", 6053)
                noise_psk = entry.data.get("noise_psk")
                if host:
                    gateways[f"{host}:{port}"] = {
                        "label": device_name,
                        "noise_psk": noise_psk,
                        "entry_id": entry.entry_id,
                    }
        return gateways

    async def _read_discovered_hydros(self) -> dict[str, str]:
        """Read discovered Hydrostations from HA state machine (no new API connection)."""
        from homeassistant.helpers import entity_registry as er

        result: dict[str, str] = {}

        # Find the entity_id for "Discovered Hydrostations" from our gateway entry
        ent_reg = er.async_get(self.hass)
        discovered_entity_id: str | None = None

        for entity in ent_reg.entities.values():
            if (
                entity.config_entry_id == self._gateway_entry_id
                and "discovered" in (entity.entity_id or "").lower()
            ):
                discovered_entity_id = entity.entity_id
                break

        if not discovered_entity_id:
            _LOGGER.warning(
                "Could not find 'Discovered Hydrostations' entity for gateway entry %s",
                self._gateway_entry_id,
            )
            return {}

        state = self.hass.states.get(discovered_entity_id)
        if not state or not state.state or state.state in ("unavailable", "unknown", ""):
            _LOGGER.warning(
                "Entity %s has no valid state: %s",
                discovered_entity_id,
                state.state if state else "missing",
            )
            return {}

        try:
            devices = json.loads(state.state)
            for d in devices:
                mac = d.get("mac", "")
                name = d.get("name", mac)
                rssi = d.get("rssi", 0)
                if mac:
                    result[mac] = f"{name} ({mac}, {rssi} dBm)"
        except (json.JSONDecodeError, KeyError) as err:
            _LOGGER.error("JSON parse error reading discovered hydros: %s", err)
            raise

        return result

    async def _write_target_mac(self, mac: str) -> None:
        """Write target MAC to ESP32 via HA text service (reuses existing connection)."""
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(self.hass)
        target_entity_id: str | None = None

        for entity in ent_reg.entities.values():
            if (
                entity.config_entry_id == self._gateway_entry_id
                and "target_mac" in (entity.entity_id or "").lower()
            ):
                target_entity_id = entity.entity_id
                break

        if not target_entity_id:
            _LOGGER.warning("Target MAC entity not found for gateway %s", self._gateway_entry_id)
            return

        await self.hass.services.async_call(
            "text",
            "set_value",
            {"entity_id": target_entity_id, "value": mac},
            blocking=True,
        )
        _LOGGER.info("Wrote target MAC %s to %s", mac, target_entity_id)
