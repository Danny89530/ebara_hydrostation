"""Sensor entities for Ebara Hydrostation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
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
    ESP_ENTITY_PRESSURE_ACTUAL,
    ESP_ENTITY_PRESSURE_TARGET,
    ESP_ENTITY_PRESSURE_START,
    ESP_ENTITY_PRESSURE_DELTA,
    ESP_ENTITY_MOTOR_FREQ,
    ESP_ENTITY_MOTOR_CURRENT,
    ESP_ENTITY_TEMPERATURE,
    ESP_ENTITY_VOLTAGE,
    ESP_ENTITY_WORKING_HOURS,
    ESP_ENTITY_FW_VERSION,
    ESP_ENTITY_HW_VERSION,
    ESP_ENTITY_WATER_LEVEL,
    ESP_ENTITY_ERROR_WORD,
    ESP_ENTITY_STATUS_WORD,
    ESP_ENTITY_ERROR_TEXT,
    ESP_ENTITY_GW_STATUS,
    ESP_ENTITY_SERIAL_NUMBER,
)
from .coordinator import EbaraCoordinator


@dataclass(frozen=True)
class EbaraSensorDescription(SensorEntityDescription):
    """Extended sensor description with ESP entity name."""
    esp_entity: str = ""
    is_numeric: bool = True


SENSOR_DESCRIPTIONS: tuple[EbaraSensorDescription, ...] = (
    EbaraSensorDescription(
        key="pressure_actual",
        name="Actual Pressure",
        esp_entity=ESP_ENTITY_PRESSURE_ACTUAL,
        native_unit_of_measurement="bar",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:gauge",
    ),
    EbaraSensorDescription(
        key="pressure_target",
        name="Target Pressure",
        esp_entity=ESP_ENTITY_PRESSURE_TARGET,
        native_unit_of_measurement="bar",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:gauge-low",
    ),
    EbaraSensorDescription(
        key="pressure_start",
        name="Start Pressure",
        esp_entity=ESP_ENTITY_PRESSURE_START,
        native_unit_of_measurement="bar",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:gauge-empty",
    ),
    EbaraSensorDescription(
        key="pressure_delta",
        name="Delta Pressure",
        esp_entity=ESP_ENTITY_PRESSURE_DELTA,
        native_unit_of_measurement="bar",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:delta",
    ),
    EbaraSensorDescription(
        key="motor_frequency",
        name="Motor Frequency",
        esp_entity=ESP_ENTITY_MOTOR_FREQ,
        native_unit_of_measurement="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:sine-wave",
    ),
    EbaraSensorDescription(
        key="motor_current",
        name="Motor Current",
        esp_entity=ESP_ENTITY_MOTOR_CURRENT,
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:current-ac",
    ),
    EbaraSensorDescription(
        key="temperature",
        name="Module Temperature",
        esp_entity=ESP_ENTITY_TEMPERATURE,
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:thermometer",
    ),
    EbaraSensorDescription(
        key="voltage",
        name="DC Bus Voltage",
        esp_entity=ESP_ENTITY_VOLTAGE,
        native_unit_of_measurement="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:flash",
    ),
    EbaraSensorDescription(
        key="working_hours",
        name="Working Hours",
        esp_entity=ESP_ENTITY_WORKING_HOURS,
        native_unit_of_measurement="h",
        device_class=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        icon="mdi:timer-outline",
    ),
    EbaraSensorDescription(
        key="fw_version",
        name="Firmware Version",
        esp_entity=ESP_ENTITY_FW_VERSION,
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        suggested_display_precision=2,
        icon="mdi:chip",
    ),
    EbaraSensorDescription(
        key="hw_version",
        name="Hardware Version",
        esp_entity=ESP_ENTITY_HW_VERSION,
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        suggested_display_precision=0,
        icon="mdi:circuit-board",
    ),
    EbaraSensorDescription(
        key="water_level",
        name="Estimated Water Level",
        esp_entity=ESP_ENTITY_WATER_LEVEL,
        native_unit_of_measurement="%",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:water-percent",
    ),
    EbaraSensorDescription(
        key="error_word",
        name="Error Word",
        esp_entity=ESP_ENTITY_ERROR_WORD,
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        suggested_display_precision=0,
        icon="mdi:alert-octagon",
    ),
    EbaraSensorDescription(
        key="status_word",
        name="Status Word",
        esp_entity=ESP_ENTITY_STATUS_WORD,
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        suggested_display_precision=0,
        icon="mdi:state-machine",
    ),
    EbaraSensorDescription(
        key="error_text",
        name="Active Errors",
        esp_entity=ESP_ENTITY_ERROR_TEXT,
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        is_numeric=False,
        icon="mdi:alert",
    ),
    EbaraSensorDescription(
        key="gw_status",
        name="Gateway Status",
        esp_entity=ESP_ENTITY_GW_STATUS,
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        is_numeric=False,
        icon="mdi:state-machine",
    ),
    EbaraSensorDescription(
        key="serial_number",
        name="Serial Number",
        esp_entity=ESP_ENTITY_SERIAL_NUMBER,
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        is_numeric=False,
        icon="mdi:barcode",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ebara sensors."""
    coordinator: EbaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EbaraSensor(coordinator, entry, desc) for desc in SENSOR_DESCRIPTIONS
    )


class EbaraSensor(SensorEntity):
    """A sensor entity backed by an ESP32 gateway entity."""

    entity_description: EbaraSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EbaraCoordinator,
        entry: ConfigEntry,
        description: EbaraSensorDescription,
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
    def native_value(self) -> Any:
        val = self._coordinator.get_value(self.entity_description.esp_entity)
        if val is None:
            return None
        if self.entity_description.is_numeric:
            try:
                fval = float(val)
            except (TypeError, ValueError):
                return None
            # suggested_display_precision only affects the *frontend* card
            # rendering — entities without a unit/device_class (e.g.
            # Firmware Version) don't get the same rounding applied there,
            # so the raw float32-imprecision (2.5999999046325684 instead of
            # 2.6) showed through unrounded. Round the actual native_value
            # itself so it's clean regardless of frontend heuristics.
            precision = self.entity_description.suggested_display_precision
            if precision is not None:
                fval = round(fval, precision)
            return fval
        return str(val)

    @property
    def available(self) -> bool:
        return self._coordinator._connected  # noqa: SLF001

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
