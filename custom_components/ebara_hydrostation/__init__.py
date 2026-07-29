"""Ebara Hydrostation integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import const
from .const import DOMAIN
from .coordinator import EbaraCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "number", "switch"]

# Every ESP32 entity our own platforms (sensor/binary_sensor/number/switch)
# already replicate under nicer names/grouping. The native "ESPHome"
# integration exposes ALL of these too (raw, generic ESPHome-device naming)
# — disable those duplicates so the user only sees one clean set. Deliberately
# does NOT include ESP_ENTITY_TARGET_MAC / ESP_ENTITY_DISCOVERED (setup-only,
# not replicated here) or the "ESP Reboot" button (no equivalent at all).
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
    const.ESP_ENTITY_WATER_LEVEL,
    const.ESP_ENTITY_ERROR_WORD,
    const.ESP_ENTITY_STATUS_WORD,
    const.ESP_ENTITY_MOTOR_RUNNING,
    const.ESP_ENTITY_MOTOR_ENABLED,
    const.ESP_ENTITY_MOTOR_ERROR,
    const.ESP_ENTITY_ERROR_TEXT,
    const.ESP_ENTITY_MOTOR_SWITCH,
    const.ESP_ENTITY_GATEWAY_ENABLE,
    const.ESP_ENTITY_SET_TARGET_PRESS,
    const.ESP_ENTITY_SET_START_PRESS,
    const.ESP_ENTITY_SET_DELTA_PRESS,
    const.ESP_ENTITY_POLL_INTERVAL,
    const.ESP_ENTITY_SERIAL_NUMBER,
    const.ESP_ENTITY_LOT_NUMBER,
}


async def _disable_duplicate_esphome_entities(hass: HomeAssistant, gateway_host: str) -> None:
    """Disable the native 'ESPHome' integration's entities that we replicate.

    Our coordinator already exposes the same data under a dedicated
    Hydrostation device with better names/grouping — leaving the raw
    ESPHome-integration entities enabled just creates confusing duplicates.
    """
    esphome_entry_id = None
    for config_entry in hass.config_entries.async_entries("esphome"):
        if config_entry.data.get("host") == gateway_host:
            esphome_entry_id = config_entry.entry_id
            break
    if esphome_entry_id is None:
        return

    entity_reg = er.async_get(hass)
    for entity in list(entity_reg.entities.values()):
        if (
            entity.config_entry_id == esphome_entry_id
            and entity.disabled_by is None
            and entity.original_name in _DUPLICATED_ESP_ENTITY_NAMES
        ):
            entity_reg.async_update_entity(
                entity.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
            )
            _LOGGER.info("Disabled duplicate native ESPHome entity: %s", entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ebara Hydrostation from a config entry."""
    coordinator = EbaraCoordinator(hass, entry)
    await coordinator.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _disable_duplicate_esphome_entities(hass, coordinator.host)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        coordinator: EbaraCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    return ok
