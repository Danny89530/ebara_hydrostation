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
ESP_ENTITY_FW_VERSION     = "Firmware Version"
ESP_ENTITY_HW_VERSION     = "Hardware Version"
ESP_ENTITY_WATER_LEVEL    = "Estimated Water Level"
ESP_ENTITY_ERROR_WORD     = "Error Word"
ESP_ENTITY_STATUS_WORD    = "Status Word"
ESP_ENTITY_MOTOR_RUNNING  = "Motor Running"
ESP_ENTITY_MOTOR_ENABLED  = "Motor Enabled"
ESP_ENTITY_MOTOR_ERROR    = "Motor Error"
ESP_ENTITY_ERROR_TEXT     = "Errors"
ESP_ENTITY_MOTOR_SWITCH   = "Motor"
ESP_ENTITY_GATEWAY_ENABLE = "Gateway Enable"
ESP_ENTITY_SET_TARGET_PRESS  = "Target Pressure Setpoint"
ESP_ENTITY_SET_START_PRESS   = "Start Pressure Setpoint"
ESP_ENTITY_SET_DELTA_PRESS   = "Delta Pressure Setpoint"
ESP_ENTITY_POLL_INTERVAL     = "Update Interval"
ESP_ENTITY_SERIAL_NUMBER     = "Serial Number"
ESP_ENTITY_LOT_NUMBER        = "Lot Number"

# Coherent bounds for the poll interval (seconds) — must match
# kUpdateIntervalMinS/kUpdateIntervalMaxS in ebara_hydrostation.cpp.
POLL_INTERVAL_MIN_S = 5
POLL_INTERVAL_MAX_S = 300
