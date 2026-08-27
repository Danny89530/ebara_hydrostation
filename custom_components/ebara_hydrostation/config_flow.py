"""Config flow for Ebara Hydrostation integration."""
from __future__ import annotations

import json
import logging
import re
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

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

# Entities this component always creates on the ESP32 gateway, used to
# recognize a gateway regardless of what the user named the device itself.
_GATEWAY_SIGNATURE_ENTITY_NAMES = {"Target MAC", "GW Status"}


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
            # Resolve the matching native ESPHome config entry by host, so
            # the entity-registry-based discovery/fallback lookups in
            # async_step_select_hydro() still work — without this,
            # _gateway_entry_id stayed None on this path (it's normally set
            # by async_step_gateway()), so those lookups matched nothing and
            # setup always failed with "no devices found" whenever the
            # gateway wasn't auto-detected and had to be entered manually.
            for entry in self.hass.config_entries.async_entries("esphome"):
                if entry.data.get("host") == self._gateway_host:
                    self._gateway_entry_id = entry.entry_id
                    self._gateway_noise_psk = entry.data.get("noise_psk")
                    break
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
        """Find ESPHome config entries that look like an Ebara Hydrostation
        gateway.

        Matches by looking for this component's own signature entities
        ("Target MAC" and "GW Status") rather than the device's own display
        name — that name is fully user-customizable (e.g. renamed to
        reflect where the gateway is physically installed), so filtering by
        a fixed "ebara-hydro" name prefix silently found nothing for any
        renamed device.
        """
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(self.hass)
        entry_signature_names: dict[str, set[str]] = {}
        for entity in ent_reg.entities.values():
            if entity.platform != "esphome":
                continue
            if entity.original_name in _GATEWAY_SIGNATURE_ENTITY_NAMES:
                entry_signature_names.setdefault(entity.config_entry_id, set()).add(
                    entity.original_name
                )

        gateways: dict[str, dict] = {}
        for entry in self.hass.config_entries.async_entries("esphome"):
            if not _GATEWAY_SIGNATURE_ENTITY_NAMES.issubset(
                entry_signature_names.get(entry.entry_id, set())
            ):
                continue
            host = entry.data.get("host", "")
            port = entry.data.get("port", 6053)
            noise_psk = entry.data.get("noise_psk")
            if not host:
                continue
            label = (
                entry.data.get("device_name")
                or entry.data.get("name")
                or entry.title
                or host
            )
            gateways[f"{host}:{port}"] = {
                "label": label,
                "noise_psk": noise_psk,
                "entry_id": entry.entry_id,
            }
        return gateways

    async def _read_discovered_hydros(self) -> dict[str, str]:
        """Read discovered Hydrostations from HA state machine (no new API connection)."""
        from homeassistant.helpers import entity_registry as er

        result: dict[str, str] = {}

        # Find the "Discovered Hydrostations" and "Target MAC" entities from
        # our gateway entry.
        ent_reg = er.async_get(self.hass)
        discovered_entity_id: str | None = None
        target_mac_entity_id: str | None = None

        for entity in ent_reg.entities.values():
            if entity.config_entry_id != self._gateway_entry_id:
                continue
            entity_id_lower = (entity.entity_id or "").lower()
            if discovered_entity_id is None and "discovered" in entity_id_lower:
                discovered_entity_id = entity.entity_id
            if target_mac_entity_id is None and "target_mac" in entity_id_lower:
                target_mac_entity_id = entity.entity_id

        if discovered_entity_id:
            state = self.hass.states.get(discovered_entity_id)
            if state and state.state and state.state not in ("unavailable", "unknown"):
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
        else:
            _LOGGER.warning(
                "Could not find 'Discovered Hydrostations' entity for gateway entry %s",
                self._gateway_entry_id,
            )

        # Fallback: a gateway that's already bonded to a pump stops scanning
        # entirely (see the ESP component's start_scan_()), so a fresh config
        # flow attempt would otherwise never find anything and association
        # would be impossible. Offer the currently configured Target MAC too,
        # so re-associating an already-paired gateway stays possible.
        if target_mac_entity_id:
            state = self.hass.states.get(target_mac_entity_id)
            if state and state.state and _MAC_RE.match(state.state):
                mac = state.state
                if mac not in result:
                    result[mac] = f"Hydrostation ({mac})"

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
