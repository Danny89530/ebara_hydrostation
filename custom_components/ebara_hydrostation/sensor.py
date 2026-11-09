"""Sensor entities for Ebara Hydrostation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EbaraConfigEntry, alarms
from .const import (
    ESP_ENTITY_DEVICE_NAME,
    ESP_ENTITY_ERROR_TEXT,
    ESP_ENTITY_FW_VERSION,
    ESP_ENTITY_GW_STATUS,
    ESP_ENTITY_HW_VERSION,
    ESP_ENTITY_MOTOR_CURRENT,
    ESP_ENTITY_MOTOR_FREQ,
    ESP_ENTITY_PRESSURE_ACTUAL,
    ESP_ENTITY_PRESSURE_DELTA,
    ESP_ENTITY_PRESSURE_START,
    ESP_ENTITY_PRESSURE_TARGET,
    ESP_ENTITY_PRESSURE_UNIT,
    ESP_ENTITY_PUMP_LOAD,
    ESP_ENTITY_PUMP_STATUS,
    ESP_ENTITY_SERIAL_NUMBER,
    ESP_ENTITY_TEMPERATURE,
    ESP_ENTITY_VOLTAGE,
    ESP_ENTITY_WORKING_HOURS,
)
from .coordinator import EbaraCoordinator
from .entity import EbaraEntity

PARALLEL_UPDATES = 0

# Alarm entries in the gateway's "Errors" text: "<code> <english text>".
_ALARM_ITEM_RE = re.compile(r"\b([EHC]\d\d\+?) ([^,]+)")


# Gateway "Pump Status" strings (same priority/meaning as the official app)
# mapped to translatable enum keys.
PUMP_STATUS_KEYS: dict[str, str] = {
    "External Stop": "external_stop",
    "Running": "running",
    "Assist Mode": "assist",
    "Standby": "standby",
    "Alarm": "alarm",
    "Pump Off": "off",
    "Offline": "offline",
}


@dataclass(frozen=True)
class EbaraSensorDescription(SensorEntityDescription):
    """Extended sensor description with ESP entity name."""
    esp_entity: str = ""
    is_numeric: bool = True


def _pressure(key: str, esp: str, icon: str | None = None) -> EbaraSensorDescription:
    # Raw resolution is 0.1 bar: one decimal, never more.
    return EbaraSensorDescription(
        key=key,
        translation_key=key,
        esp_entity=esp,
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon=icon,
    )


SENSOR_DESCRIPTIONS: tuple[EbaraSensorDescription, ...] = (
    _pressure("pressure_actual", ESP_ENTITY_PRESSURE_ACTUAL),
    _pressure("pressure_target", ESP_ENTITY_PRESSURE_TARGET),
    # Read-only: equals target − delta.
    _pressure("pressure_start", ESP_ENTITY_PRESSURE_START),
    _pressure("pressure_delta", ESP_ENTITY_PRESSURE_DELTA),
    EbaraSensorDescription(
        key="motor_frequency",
        translation_key="motor_frequency",
        esp_entity=ESP_ENTITY_MOTOR_FREQ,
        # Unit not confirmed by the official app (never displayed): raw value.
        native_unit_of_measurement=None,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:sine-wave",
    ),
    EbaraSensorDescription(
        key="motor_current",
        translation_key="motor_current",
        esp_entity=ESP_ENTITY_MOTOR_CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    EbaraSensorDescription(
        key="temperature",
        translation_key="temperature",
        esp_entity=ESP_ENTITY_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    EbaraSensorDescription(
        key="voltage",
        translation_key="voltage",
        esp_entity=ESP_ENTITY_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    EbaraSensorDescription(
        key="working_hours",
        translation_key="working_hours",
        esp_entity=ESP_ENTITY_WORKING_HOURS,
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    EbaraSensorDescription(
        key="pump_load",
        translation_key="pump_load",
        esp_entity=ESP_ENTITY_PUMP_LOAD,
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:speedometer",
    ),
    EbaraSensorDescription(
        key="pump_status",
        translation_key="pump_status",
        esp_entity=ESP_ENTITY_PUMP_STATUS,
        is_numeric=False,
        device_class=SensorDeviceClass.ENUM,
        options=list(PUMP_STATUS_KEYS.values()),
        icon="mdi:pump",
    ),
    EbaraSensorDescription(
        key="error_text",
        translation_key="error_text",
        esp_entity=ESP_ENTITY_ERROR_TEXT,
        is_numeric=False,
        icon="mdi:alert",
    ),
    EbaraSensorDescription(
        key="fw_version",
        translation_key="fw_version",
        esp_entity=ESP_ENTITY_FW_VERSION,
        is_numeric=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chip",
    ),
    EbaraSensorDescription(
        key="hw_version",
        translation_key="hw_version",
        esp_entity=ESP_ENTITY_HW_VERSION,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        icon="mdi:circuit-board",
    ),
    EbaraSensorDescription(
        key="pressure_unit",
        translation_key="pressure_unit",
        esp_entity=ESP_ENTITY_PRESSURE_UNIT,
        is_numeric=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:gauge",
    ),
    EbaraSensorDescription(
        key="device_name",
        translation_key="device_name",
        esp_entity=ESP_ENTITY_DEVICE_NAME,
        is_numeric=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:bluetooth",
    ),
    EbaraSensorDescription(
        key="gw_status",
        translation_key="gw_status",
        esp_entity=ESP_ENTITY_GW_STATUS,
        is_numeric=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
    ),
    EbaraSensorDescription(
        key="serial_number",
        translation_key="serial_number",
        esp_entity=ESP_ENTITY_SERIAL_NUMBER,
        is_numeric=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:barcode",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EbaraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ebara sensors."""
    coordinator = entry.runtime_data
    async_add_entities(EbaraSensor(coordinator, desc) for desc in SENSOR_DESCRIPTIONS)


class EbaraSensor(EbaraEntity, SensorEntity):
    """A sensor entity backed by an ESP32 gateway entity."""

    entity_description: EbaraSensorDescription

    def __init__(self, coordinator: EbaraCoordinator, description: EbaraSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    def _language(self) -> str:
        return self.hass.config.language if self.hass else "en"

    def _active_alarms(self) -> list[dict[str, str]] | None:
        """Active alarms from the gateway's alarm text (it lists codes only
        while the status-word alarm bit is set, like the official app),
        translated with the app's own texts in the HA language. None while
        the pump is offline/unknown."""
        text = self.coordinator.get_value(ESP_ENTITY_ERROR_TEXT)
        if text is None or str(text).startswith("Unknown"):
            return None
        items = _ALARM_ITEM_RE.findall(str(text))
        psi = str(self.coordinator.get_value(ESP_ENTITY_PRESSURE_UNIT) or "") == "psi"
        return alarms.decode_codes(items, psi=psi, lang=self._language())

    def _alarm_without_code(self) -> bool:
        return str(self.coordinator.get_value(ESP_ENTITY_ERROR_TEXT) or "").startswith("Alarm")

    def _localized_alarms(self) -> str | None:
        active = self._active_alarms()
        if active is None:
            return None
        italian = self._language().startswith("it")
        if not active:
            if self._alarm_without_code():
                return "Allarme (codice non disponibile)" if italian else "Alarm (no code)"
            return "Nessun allarme attivo" if italian else "No active alarms"
        return ", ".join(f"{a['code']} {a['text']}" for a in active)[:255]

    @property
    def native_value(self) -> Any:
        if self.entity_description.key == "error_text":
            return self._localized_alarms()
        val = self.coordinator.get_value(self.entity_description.esp_entity)
        if val is None:
            return None
        if self.entity_description.is_numeric:
            try:
                fval = float(val)
            except (TypeError, ValueError):
                return None
            # Round the value itself (the gateway sends float32 values).
            precision = self.entity_description.suggested_display_precision
            if precision is not None:
                fval = round(fval, precision)
            return fval
        if self.entity_description.key == "pump_status":
            return PUMP_STATUS_KEYS.get(str(val))
        return str(val)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Alarm details (code, severity, text, remedy) like the app's alarm list."""
        if self.entity_description.key != "error_text":
            return None
        active = self._active_alarms()
        if active is None:
            return None
        return {"alarm_active": bool(active) or self._alarm_without_code(), "alarms": active}
