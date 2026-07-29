"""Binary sensor entities for Ebara Hydrostation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HYDRO_MAC,
    CONF_HYDRO_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    ESP_ENTITY_MOTOR_RUNNING,
    ESP_ENTITY_MOTOR_ENABLED,
    ESP_ENTITY_MOTOR_ERROR,
)
from .coordinator import EbaraCoordinator


@dataclass(frozen=True)
class EbaraBinarySensorDescription(BinarySensorEntityDescription):
    esp_entity: str = ""


BINARY_SENSOR_DESCRIPTIONS: tuple[EbaraBinarySensorDescription, ...] = (
    EbaraBinarySensorDescription(
        key="motor_running",
        name="Motor Running",
        esp_entity=ESP_ENTITY_MOTOR_RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:pump",
    ),
    EbaraBinarySensorDescription(
        key="motor_enabled",
        name="Motor Enabled",
        esp_entity=ESP_ENTITY_MOTOR_ENABLED,
        device_class=None,
        icon="mdi:power",
    ),
    EbaraBinarySensorDescription(
        key="motor_error",
        name="Motor Error",
        esp_entity=ESP_ENTITY_MOTOR_ERROR,
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ebara binary sensors."""
    coordinator: EbaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EbaraBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class EbaraBinarySensor(BinarySensorEntity):
    """Binary sensor backed by an ESP32 gateway entity."""

    entity_description: EbaraBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EbaraCoordinator,
        entry: ConfigEntry,
        description: EbaraBinarySensorDescription,
    ) -> None:
        self.entity_description = description
        self._coordinator = coordinator
        mac = entry.data[CONF_HYDRO_MAC]
        hydro_name = entry.data[CONF_HYDRO_NAME]
        self._attr_unique_id = f"{mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=hydro_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool | None:
        val = self._coordinator.get_value(self.entity_description.esp_entity)
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        return bool(val)

    @property
    def available(self) -> bool:
        return self._coordinator._connected  # noqa: SLF001

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
