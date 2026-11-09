"""Binary sensor entities for Ebara Hydrostation."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EbaraConfigEntry
from .const import (
    ESP_ENTITY_EXTERNAL_STOP,
    ESP_ENTITY_MOTOR_ENABLED,
    ESP_ENTITY_MOTOR_ERROR,
    ESP_ENTITY_MOTOR_RUNNING,
    ESP_ENTITY_STATUS_BIT10,
)
from .coordinator import EbaraCoordinator
from .entity import EbaraEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EbaraBinarySensorDescription(BinarySensorEntityDescription):
    esp_entity: str


BINARY_SENSOR_DESCRIPTIONS: tuple[EbaraBinarySensorDescription, ...] = (
    EbaraBinarySensorDescription(
        key="motor_running",
        translation_key="motor_running",
        esp_entity=ESP_ENTITY_MOTOR_RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:pump",
    ),
    EbaraBinarySensorDescription(
        key="motor_enabled",
        translation_key="motor_enabled",
        esp_entity=ESP_ENTITY_MOTOR_ENABLED,
        icon="mdi:power",
    ),
    EbaraBinarySensorDescription(
        key="motor_error",
        translation_key="motor_error",
        esp_entity=ESP_ENTITY_MOTOR_ERROR,
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle",
    ),
    # Status bit 11 = 0: external stop input active (highest-priority state in the app).
    EbaraBinarySensorDescription(
        key="external_stop",
        translation_key="external_stop",
        esp_entity=ESP_ENTITY_EXTERNAL_STOP,
        icon="mdi:hand-back-left",
    ),
    # Status word bit 10: not decoded by the official app nor documented in
    # the pump manual. Raw, not interpreted.
    EbaraBinarySensorDescription(
        key="status_bit10",
        translation_key="status_bit10",
        esp_entity=ESP_ENTITY_STATUS_BIT10,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:help-circle-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EbaraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ebara binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        EbaraBinarySensor(coordinator, desc) for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class EbaraBinarySensor(EbaraEntity, BinarySensorEntity):
    """Binary sensor backed by an ESP32 gateway entity."""

    entity_description: EbaraBinarySensorDescription

    def __init__(self, coordinator: EbaraCoordinator, description: EbaraBinarySensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        val = self.coordinator.get_value(self.entity_description.esp_entity)
        return None if val is None else bool(val)
