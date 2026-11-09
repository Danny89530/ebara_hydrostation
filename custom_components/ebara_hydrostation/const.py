"""Constants for the Ebara Hydrostation integration."""
DOMAIN = "ebara_hydrostation"
MANUFACTURER = "Ebara"
MODEL = "Hydrostation"

# Config entry keys
CONF_GATEWAY_HOST = "gateway_host"
CONF_GATEWAY_PORT = "gateway_port"
CONF_GATEWAY_NOISE_PSK = "gateway_noise_psk"
# ESPHome device name, used as the mDNS name ReconnectLogic tracks so the
# connection follows the gateway if its IP changes. May be unset, in which
# case the coordinator falls back to plain host/IP tracking.
CONF_GATEWAY_DEVICE_NAME = "gateway_device_name"
CONF_HYDRO_MAC = "hydro_mac"
CONF_HYDRO_NAME = "hydro_name"
# entry_id of the native ESPHome config entry of the gateway (older entries
# lack it: the gateway host is used as a fallback).
CONF_GATEWAY_ENTRY_ID = "gateway_entry_id"
# Set once the duplicated native ESPHome entities have been disabled, so a
# user who re-enables one of them later is not overridden at every restart.
CONF_ESPHOME_DUPLICATES_DISABLED = "esphome_duplicates_disabled"

# ESPHome entity names on the gateway (must match YAML names exactly)
ESP_ENTITY_DISCOVERED     = "Discovered Hydrostations"
ESP_ENTITY_GW_STATUS      = "GW Status"
ESP_ENTITY_TARGET_MAC     = "Target MAC"
ESP_ENTITY_PRESSURE_ACTUAL  = "Actual Pressure"
ESP_ENTITY_PRESSURE_TARGET  = "Target Pressure"
ESP_ENTITY_PRESSURE_START   = "Start Pressure"
ESP_ENTITY_PRESSURE_DELTA   = "Delta Pressure"
ESP_ENTITY_MOTOR_FREQ     = "Motor Frequency"
ESP_ENTITY_MOTOR_CURRENT  = "Motor Current"
ESP_ENTITY_TEMPERATURE    = "Module Temperature"
ESP_ENTITY_VOLTAGE        = "DC Bus Voltage"
ESP_ENTITY_WORKING_HOURS  = "Working Hours"
ESP_ENTITY_FW_VERSION     = "Firmware Version"          # text "HH.LL" (app format)
ESP_ENTITY_HW_VERSION     = "Hardware Version"
ESP_ENTITY_PUMP_LOAD      = "Estimated Pump Load"       # app "FREQUENCY SPEED" %
ESP_ENTITY_PUMP_STATUS    = "Pump Status"
ESP_ENTITY_PRESSURE_UNIT  = "Pressure Unit"
ESP_ENTITY_DEVICE_NAME    = "Pump Device Name"
ESP_ENTITY_MOTOR_RUNNING  = "Motor Running"
ESP_ENTITY_MOTOR_ENABLED  = "Motor Enabled"
ESP_ENTITY_MOTOR_ERROR    = "Motor Error"
ESP_ENTITY_EXTERNAL_STOP  = "External Stop"
ESP_ENTITY_STATUS_BIT10   = "Status Bit 10 (undocumented)"
ESP_ENTITY_ERROR_TEXT     = "Errors"
ESP_ENTITY_MOTOR_SWITCH   = "Motor"
ESP_ENTITY_GATEWAY_ENABLE = "Gateway Enable"
ESP_ENTITY_SET_TARGET_PRESS  = "Target Pressure Setpoint"
ESP_ENTITY_SET_DELTA_PRESS   = "Delta Pressure Setpoint"
ESP_ENTITY_POLL_INTERVAL     = "Update Interval"
ESP_ENTITY_SERIAL_NUMBER     = "Serial Number"

# Gateway entities added in version 2.0 of the ESPHome component. If any is
# missing, the gateway runs an older component or its YAML lacks the new keys:
# a repair issue tells the user what to update.
GATEWAY_V2_ENTITIES = (
    ESP_ENTITY_PUMP_STATUS,
    ESP_ENTITY_PUMP_LOAD,
    ESP_ENTITY_PRESSURE_UNIT,
    ESP_ENTITY_EXTERNAL_STOP,
    ESP_ENTITY_DEVICE_NAME,
)
GATEWAY_CHANGELOG_URL = (
    "https://github.com/Danny89530/esphome-ebara-hydrostation/blob/main/CHANGELOG.md"
)

# Coherent bounds for the poll interval (seconds) — must match
# kUpdateIntervalMinS/kUpdateIntervalMaxS in ebara_hydrostation.cpp.
POLL_INTERVAL_MIN_S = 2
POLL_INTERVAL_MAX_S = 300
