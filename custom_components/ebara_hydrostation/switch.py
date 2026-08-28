"""Switch entity for Ebara Hydrostation motor control."""
from __future__ import annotations

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HYDRO_MAC,
    CONF_HYDRO_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    ESP_ENTITY_MOTOR_SWITCH,
    ESP_ENTITY_GATEWAY_ENABLE,
)
from .coordinator import EbaraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the motor and gateway-enable switch entities."""
    coordinator: EbaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [EbaraMotorSwitch(coordinator, entry), EbaraGatewayEnableSwitch(coordinator, entry)]
    )


class EbaraMotorSwitch(SwitchEntity):
    """Switch entity that controls the Hydrostation motor via ESP32."""

    _attr_has_entity_name = True
    _attr_name = "Motor"
    _attr_icon = "mdi:pump"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: EbaraCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        mac = entry.data[CONF_HYDRO_MAC]
        hydro_name = entry.data[CONF_HYDRO_NAME]
        self._attr_unique_id = f"{mac}_motor_switch"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=hydro_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the motor's automatic control is enabled."""
        val = self._coordinator.get_value(ESP_ENTITY_MOTOR_SWITCH)
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        return bool(val)

    @property
    def available(self) -> bool:
        return self._coordinator._connected  # noqa: SLF001

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the motor on."""
        await self._coordinator.async_send_command(ESP_ENTITY_MOTOR_SWITCH, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the motor off."""
        await self._coordinator.async_send_command(ESP_ENTITY_MOTOR_SWITCH, False)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )


class EbaraGatewayEnableSwitch(SwitchEntity):
    """Master enable/disable switch for the ESP32 gateway's BLE connection."""

    _attr_has_entity_name = True
    _attr_name = "Gateway Enable"
    _attr_icon = "mdi:bluetooth-connect"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EbaraCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        mac = entry.data[CONF_HYDRO_MAC]
        hydro_name = entry.data[CONF_HYDRO_NAME]
        self._attr_unique_id = f"{mac}_gateway_enable"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=hydro_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool | None:
        val = self._coordinator.get_value(ESP_ENTITY_GATEWAY_ENABLE)
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        return bool(val)

    @property
    def available(self) -> bool:
        return self._coordinator._connected  # noqa: SLF001

    async def async_turn_on(self, **kwargs) -> None:
        await self._coordinator.async_send_command(ESP_ENTITY_GATEWAY_ENABLE, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.async_send_command(ESP_ENTITY_GATEWAY_ENABLE, False)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
