"""Ebara Hydrostation integration for Home Assistant."""
from __future__ import annotations

import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from . import const
from .const import (
    CONF_ESPHOME_DUPLICATES_DISABLED,
    CONF_GATEWAY_ENTRY_ID,
    CONF_GATEWAY_HOST,
    CONF_HYDRO_MAC,
    CONF_HYDRO_NAME,
    DOMAIN,
)
from .coordinator import EbaraCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
]

type EbaraConfigEntry = ConfigEntry[EbaraCoordinator]

# Every gateway entity our own platforms already replicate under nicer names
# and a dedicated device. The native ESPHome integration exposes them too:
# those duplicates are disabled once. Deliberately NOT included: Target MAC /
# Discovered Hydrostations (setup only, not replicated) and the ESP restart
# switch (no equivalent here).
_DUPLICATED_ESP_ENTITY_NAMES = {
    const.ESP_ENTITY_GW_STATUS,
    const.ESP_ENTITY_PRESSURE_ACTUAL,
    const.ESP_ENTITY_PRESSURE_TARGET,
    const.ESP_ENTITY_PRESSURE_START,
    const.ESP_ENTITY_PRESSURE_DELTA,
    const.ESP_ENTITY_MOTOR_FREQ,
    const.ESP_ENTITY_MOTOR_CURRENT,
    const.ESP_ENTITY_TEMPERATURE,
    const.ESP_ENTITY_VOLTAGE,
    const.ESP_ENTITY_WORKING_HOURS,
    const.ESP_ENTITY_FW_VERSION,
    const.ESP_ENTITY_HW_VERSION,
    const.ESP_ENTITY_PUMP_LOAD,
    const.ESP_ENTITY_PUMP_STATUS,
    const.ESP_ENTITY_PRESSURE_UNIT,
    const.ESP_ENTITY_DEVICE_NAME,
    const.ESP_ENTITY_MOTOR_RUNNING,
    const.ESP_ENTITY_MOTOR_ENABLED,
    const.ESP_ENTITY_MOTOR_ERROR,
    const.ESP_ENTITY_EXTERNAL_STOP,
    const.ESP_ENTITY_STATUS_BIT10,
    const.ESP_ENTITY_ERROR_TEXT,
    const.ESP_ENTITY_MOTOR_SWITCH,
    const.ESP_ENTITY_GATEWAY_ENABLE,
    const.ESP_ENTITY_SET_TARGET_PRESS,
    const.ESP_ENTITY_SET_DELTA_PRESS,
    const.ESP_ENTITY_POLL_INTERVAL,
    const.ESP_ENTITY_SERIAL_NUMBER,
}

# Entity keys exposed by earlier versions and since removed (raw data,
# misleading or unsupported entities). Their registry entries are removed on
# setup so upgrades do not leave orphaned "not provided" entities behind.
_REMOVED_ENTITY_KEYS = (
    "water_level",          # renamed: pump_load ("FREQUENCY SPEED" % of the app)
    "set_start_pressure",   # sm-0002 is never sent by the official app
    "error_word",           # raw data: "Active alarms" carries the decoded alarms
    "status_word",          # raw data: decoded into the pump status entities
)


def _esphome_entry_id(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """entry_id of the gateway's native ESPHome config entry."""
    saved = entry.data.get(CONF_GATEWAY_ENTRY_ID)
    if saved and hass.config_entries.async_get_entry(saved) is not None:
        return saved
    host = entry.data.get(CONF_GATEWAY_HOST)
    for esphome_entry in hass.config_entries.async_entries("esphome"):
        if esphome_entry.data.get("host") == host:
            return esphome_entry.entry_id
    return None


def _duplicate_esphome_entities(hass: HomeAssistant, entry: ConfigEntry) -> list[er.RegistryEntry]:
    esphome_entry_id = _esphome_entry_id(hass, entry)
    if esphome_entry_id is None:
        return []
    entity_reg = er.async_get(hass)
    return [
        entity
        for entity in er.async_entries_for_config_entry(entity_reg, esphome_entry_id)
        if entity.original_name in _DUPLICATED_ESP_ENTITY_NAMES
    ]


@callback
def _disable_duplicate_esphome_entities_once(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Disable the native ESPHome entities we replicate — only the first time.

    Done once per config entry: a user who deliberately re-enables one of them
    is not overridden at every restart.
    """
    if entry.data.get(CONF_ESPHOME_DUPLICATES_DISABLED):
        return
    duplicates = _duplicate_esphome_entities(hass, entry)
    if not duplicates:
        return  # ESPHome entities not registered yet: retry at the next setup
    entity_reg = er.async_get(hass)
    for entity in duplicates:
        if entity.disabled_by is None:
            entity_reg.async_update_entity(
                entity.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
            )
            _LOGGER.info("Disabled duplicate native ESPHome entity: %s", entity.entity_id)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_ESPHOME_DUPLICATES_DISABLED: True}
    )


@callback
def _remove_obsolete_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    entity_reg = er.async_get(hass)
    mac = entry.data.get(CONF_HYDRO_MAC)
    obsolete = {f"{mac}_{key}" for key in _REMOVED_ENTITY_KEYS}
    for entity in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
        if entity.unique_id in obsolete:
            entity_reg.async_remove(entity.entity_id)
            _LOGGER.info("Removed obsolete entity %s", entity.entity_id)


@callback
def _track_device_info(hass: HomeAssistant, entry: EbaraConfigEntry) -> None:
    """Keep the pump device up to date with what the gateway reads: firmware
    and hardware version, serial number, and the pump's Bluetooth name when
    the entry still has the generic placeholder name."""
    coordinator = entry.runtime_data
    device_reg = dr.async_get(hass)
    last: dict[str, str | None] = {}

    @callback
    def _update() -> None:
        fw = coordinator.get_value(const.ESP_ENTITY_FW_VERSION)
        hw = coordinator.get_value(const.ESP_ENTITY_HW_VERSION)
        serial = coordinator.get_value(const.ESP_ENTITY_SERIAL_NUMBER)
        changes: dict[str, str] = {}
        if fw:
            changes["sw_version"] = str(fw)
        if hw is not None:
            changes["hw_version"] = str(int(hw))
        if serial and serial != "not programmed":
            changes["serial_number"] = str(serial)
        pump_name = coordinator.get_value(const.ESP_ENTITY_DEVICE_NAME)
        if (
            entry.data.get(CONF_HYDRO_NAME) == _GENERIC_PUMP_NAME
            and isinstance(pump_name, str)
            and pump_name.startswith("HYDRO")
        ):
            changes["name"] = pump_name
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_HYDRO_NAME: pump_name},
                title=pump_name if entry.title == _GENERIC_PUMP_NAME else entry.title,
            )
        if not changes or all(last.get(k) == v for k, v in changes.items()):
            return
        # The entry owns exactly one device: the pump.
        identifier = (DOMAIN, entry.data[CONF_HYDRO_MAC])
        device = next(
            (
                d
                for d in dr.async_entries_for_config_entry(device_reg, entry.entry_id)
                if identifier in d.identifiers
            ),
            None,
        )
        if device is None:
            return
        device_reg.async_update_device(device.id, **changes)
        last.update(changes)

    entry.async_on_unload(coordinator.async_add_listener(_update))


# Pump name as stored by the version 1.x config flow: the list label, with
# the MAC and possibly the signal strength, instead of the plain name —
# "HYDRO_1234 (AA:BB:CC:DD:EE:FF, -70 dBm)" or "Hydrostation (AA:BB:CC:DD:EE:FF)".
_LEGACY_NAME_RE = re.compile(
    r"^(?P<name>.+?) \((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?:, -?\d+ dBm)?\)$"
)
# Placeholder name used when the pump's Bluetooth name was not known at setup:
# replaced by the real name ("HYDRO_xxxx") as soon as the gateway reports it.
_GENERIC_PUMP_NAME = "Hydrostation"


@callback
def _migrate_entry_data(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Bring entries created by version 1.x up to date.

    - remember the gateway's ESPHome config entry (lookups survive an IP change);
    - use the plain pump name for the entry and its device.
    """
    data = dict(entry.data)
    title = entry.title
    if not data.get(CONF_GATEWAY_ENTRY_ID):
        if (esphome_entry_id := _esphome_entry_id(hass, entry)) is not None:
            data[CONF_GATEWAY_ENTRY_ID] = esphome_entry_id
    if (match := _LEGACY_NAME_RE.match(data.get(CONF_HYDRO_NAME) or "")) is not None:
        data[CONF_HYDRO_NAME] = match["name"]
        if title == entry.data.get(CONF_HYDRO_NAME):
            title = match["name"]
    if data != entry.data or title != entry.title:
        hass.config_entries.async_update_entry(entry, data=data, title=title)


async def async_setup_entry(hass: HomeAssistant, entry: EbaraConfigEntry) -> bool:
    """Set up Ebara Hydrostation from a config entry."""
    _remove_obsolete_entities(hass, entry)
    _migrate_entry_data(hass, entry)
    coordinator = EbaraCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _track_device_info(hass, entry)
    _disable_duplicate_esphome_entities_once(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EbaraConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_stop()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-enable the native ESPHome entities we disabled when the
    integration is removed (otherwise they would stay hidden forever)."""
    ir.async_delete_issue(hass, DOMAIN, f"gateway_outdated_{entry.entry_id}")
    entity_reg = er.async_get(hass)
    for entity in _duplicate_esphome_entities(hass, entry):
        if entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
            entity_reg.async_update_entity(entity.entity_id, disabled_by=None)
            _LOGGER.info("Re-enabled native ESPHome entity: %s", entity.entity_id)
