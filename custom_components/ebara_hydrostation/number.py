"""Number entities for Ebara Hydrostation (pressure setpoints, poll interval)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfPressure, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EbaraConfigEntry
from .const import (
    ESP_ENTITY_POLL_INTERVAL,
    ESP_ENTITY_SET_DELTA_PRESS,
    ESP_ENTITY_SET_TARGET_PRESS,
    POLL_INTERVAL_MAX_S,
    POLL_INTERVAL_MIN_S,
)
from .coordinator import EbaraCoordinator
from .entity import EbaraEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EbaraNumberDescription(NumberEntityDescription):
    esp_entity: str
    # Decimals the value is rounded to (the gateway sends float32 values).
    decimals: int = 0


NUMBER_DESCRIPTIONS: tuple[EbaraNumberDescription, ...] = (
    # HYDRO limits of the official app (target 2.0–5.5 bar, delta 0.5–2.0 bar).
    EbaraNumberDescription(
        key="set_target_pressure",
        translation_key="set_target_pressure",
        esp_entity=ESP_ENTITY_SET_TARGET_PRESS,
        native_min_value=2.0,
        native_max_value=5.5,
        native_step=0.1,
        decimals=1,
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=NumberDeviceClass.PRESSURE,
        icon="mdi:gauge",
        mode=NumberMode.SLIDER,
    ),
    EbaraNumberDescription(
        key="set_delta_pressure",
        translation_key="set_delta_pressure",
        esp_entity=ESP_ENTITY_SET_DELTA_PRESS,
        native_min_value=0.5,
        native_max_value=2.0,
        native_step=0.1,
        decimals=1,
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=NumberDeviceClass.PRESSURE,
        icon="mdi:delta",
        mode=NumberMode.SLIDER,
    ),
    EbaraNumberDescription(
        key="poll_interval",
        translation_key="poll_interval",
        esp_entity=ESP_ENTITY_POLL_INTERVAL,
        native_min_value=POLL_INTERVAL_MIN_S,
        native_max_value=POLL_INTERVAL_MAX_S,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        icon="mdi:timer-sync",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EbaraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ebara number entities."""
    coordinator = entry.runtime_data
    async_add_entities(EbaraNumber(coordinator, desc) for desc in NUMBER_DESCRIPTIONS)


class EbaraNumber(EbaraEntity, NumberEntity):
    """A writable number mirroring a gateway number entity."""

    entity_description: EbaraNumberDescription

    def __init__(self, coordinator: EbaraCoordinator, description: EbaraNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Current value as reported by the gateway (None = unknown)."""
        val = self.coordinator.get_value(self.entity_description.esp_entity)
        if val is None:
            return None  # pump offline / not read yet: never a stale value
        try:
            return round(float(val), self.entity_description.decimals)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Send the new value; the state follows the gateway's read-back."""
        await self.coordinator.async_send_command(self.entity_description.esp_entity, value)
