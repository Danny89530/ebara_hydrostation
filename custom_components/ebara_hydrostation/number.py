"""Number entities for Ebara Hydrostation writable pressure setpoints."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
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
    ESP_ENTITY_SET_TARGET_PRESS,
    ESP_ENTITY_SET_START_PRESS,
    ESP_ENTITY_SET_DELTA_PRESS,
    ESP_ENTITY_POLL_INTERVAL,
    POLL_INTERVAL_MIN_S,
    POLL_INTERVAL_MAX_S,
)
from .coordinator import EbaraCoordinator


@dataclass(frozen=True)
class EbaraNumberDescription(NumberEntityDescription):
    esp_entity: str = ""


NUMBER_DESCRIPTIONS: tuple[EbaraNumberDescription, ...] = (
    EbaraNumberDescription(
        key="set_target_pressure",
        name="Set Target Pressure",
        esp_entity=ESP_ENTITY_SET_TARGET_PRESS,
        native_min_value=2.0,
        native_max_value=5.5,
        native_step=0.1,
        native_unit_of_measurement="bar",
        device_class=NumberDeviceClass.PRESSURE,
        icon="mdi:gauge",
        mode=NumberMode.SLIDER,
    ),
    EbaraNumberDescription(
        key="set_start_pressure",
        name="Set Start Pressure",
        esp_entity=ESP_ENTITY_SET_START_PRESS,
        native_min_value=1.0,
        native_max_value=5.5,
        native_step=0.1,
        native_unit_of_measurement="bar",
        device_class=NumberDeviceClass.PRESSURE,
        icon="mdi:gauge-empty",
        mode=NumberMode.SLIDER,
    ),
    EbaraNumberDescription(
        key="set_delta_pressure",
        name="Set Delta Pressure",
        esp_entity=ESP_ENTITY_SET_DELTA_PRESS,
        native_min_value=0.5,
        native_max_value=2.0,
        native_step=0.1,
        native_unit_of_measurement="bar",
        device_class=NumberDeviceClass.PRESSURE,
        icon="mdi:delta",
        mode=NumberMode.SLIDER,
    ),
    EbaraNumberDescription(
        key="poll_interval",
        name="Update Interval",
        esp_entity=ESP_ENTITY_POLL_INTERVAL,
        native_min_value=POLL_INTERVAL_MIN_S,
        native_max_value=POLL_INTERVAL_MAX_S,
        native_step=1,
        native_unit_of_measurement="s",
        device_class=NumberDeviceClass.DURATION,
        icon="mdi:timer-sync",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ebara number entities."""
    coordinator: EbaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EbaraNumber(coordinator, entry, desc) for desc in NUMBER_DESCRIPTIONS
    )


class EbaraNumber(RestoreNumber, NumberEntity):
    """A writable number entity for Ebara pressure setpoints."""

    entity_description: EbaraNumberDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EbaraCoordinator,
        entry: ConfigEntry,
        description: EbaraNumberDescription,
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
    def native_value(self) -> float | None:
        """Return current value from coordinator (mirrors ESP32 state)."""
        val = self._coordinator.get_value(self.entity_description.esp_entity)
        if val is None:
            return self._attr_native_value  # restored value
        try:
            fval = float(val)
        except (TypeError, ValueError):
            return None
        # NumberEntityDescription has no suggested_display_precision, so raw
        # float32 imprecision (e.g. 2.5999999046325684) would show through
        # uncorrected. Round to the same precision as native_step instead.
        step = self.entity_description.native_step
        if step:
            step_str = str(step)
            decimals = len(step_str.split(".")[1]) if "." in step_str else 0
            fval = round(fval, decimals)
        return fval

    @property
    def available(self) -> bool:
        return self._coordinator._connected  # noqa: SLF001

    async def async_set_native_value(self, value: float) -> None:
        """Send updated setpoint to ESP32 via coordinator."""
        await self._coordinator.async_send_command(
            self.entity_description.esp_entity, value
        )
        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore previous value and subscribe to coordinator updates."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last and last.native_value is not None:
            self._attr_native_value = last.native_value
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
