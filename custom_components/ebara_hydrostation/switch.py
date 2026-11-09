"""Switch entities for Ebara Hydrostation (motor, gateway enable)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EbaraConfigEntry
from .const import ESP_ENTITY_GATEWAY_ENABLE, ESP_ENTITY_MOTOR_SWITCH
from .coordinator import EbaraCoordinator
from .entity import EbaraEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EbaraSwitchDescription(SwitchEntityDescription):
    esp_entity: str
    unique_suffix: str


SWITCH_DESCRIPTIONS: tuple[EbaraSwitchDescription, ...] = (
    # Automatic control of the pump (sm-0005): not whether the motor spins.
    EbaraSwitchDescription(
        key="motor",
        translation_key="motor",
        esp_entity=ESP_ENTITY_MOTOR_SWITCH,
        unique_suffix="motor_switch",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:pump",
    ),
    # Master enable of the gateway's BLE connection to the pump.
    EbaraSwitchDescription(
        key="gateway_enable",
        translation_key="gateway_enable",
        esp_entity=ESP_ENTITY_GATEWAY_ENABLE,
        unique_suffix="gateway_enable",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:bluetooth-connect",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EbaraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch entities."""
    coordinator = entry.runtime_data
    async_add_entities(EbaraSwitch(coordinator, desc) for desc in SWITCH_DESCRIPTIONS)


class EbaraSwitch(EbaraEntity, SwitchEntity):
    """Switch mirroring a gateway switch entity."""

    entity_description: EbaraSwitchDescription

    def __init__(self, coordinator: EbaraCoordinator, description: EbaraSwitchDescription) -> None:
        super().__init__(coordinator, description.unique_suffix)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        val = self.coordinator.get_value(self.entity_description.esp_entity)
        return None if val is None else bool(val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(self.entity_description.esp_entity, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(self.entity_description.esp_entity, False)
