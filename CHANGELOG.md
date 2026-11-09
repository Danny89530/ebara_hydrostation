# Changelog

## 2.0.0

Requires the ESPHome gateway component
[esphome-ebara-hydrostation](https://github.com/Danny89530/esphome-ebara-hydrostation)
**2.0.0** or newer, with the new entities added to its YAML (see its
changelog). Home Assistant 2025.2 or newer.

### Upgrading from 1.x

Nothing to do in Home Assistant: install the update and restart. The existing
entry, entity IDs and history are kept, and on the first start:

- the obsolete entities *Estimated Water Level*, *Error Word*, *Status Word*
  and *Set Start Pressure* are removed;
- the new entities are added;
- an entry named after the old setup label ("HYDRO_xxxx (MAC, -NN dBm)") is
  renamed to the pump name ("HYDRO_xxxx"), together with its device.

Then update the ESPHome gateway. Until it runs component 2.x with the new
entities in its YAML, a **repair notice** ("Ebara gateway needs updating")
lists the missing entities, and the entities that depend on them stay
unknown. The notice disappears by itself once the gateway is updated.

### Added

- **Pump status** (Running, Standby, Assist mode, External stop, Alarm, Pump
  off, Offline), **External stop**, **Pressure unit**, **Pump device name**
  and a diagnostic **Status bit 10** (raw, not decoded by the app).
- **Active alarms** with the official app's texts in English and Italian;
  severity and remedy of each alarm as attributes (`alarm_active`, `alarms`).
  Codes unknown to the app are shown with the gateway's text.
- **Estimated pump load** (the app's "FREQUENCY SPEED" %), replacing
  *Estimated Water Level*.
- Firmware version, hardware version and serial number of the pump on the
  device page.
- Italian translation of every entity name and of the pump states; translated
  error messages for failed commands.
- Repair notice when the gateway runs an outdated component or YAML.

### Changed

- Values the gateway cannot read (pump offline, gateway disabled) are shown
  as **unknown** instead of the last reading; setpoints no longer fall back to
  a stored value.
- **Motor frequency** has no unit any more (the "Hz" unit was not confirmed
  by the app: the value is raw) and **Firmware version** is a text in the
  app's format (`01.04`). Home Assistant may report a long-term statistics
  issue for the motor frequency (unit changed): choose to delete the old
  statistics.
- Update interval range 2–300 s (live values; slow values every 60 s on the
  gateway).
- Setup wizard:
  - lists only supported (HYDRO) pumps;
  - names the entry and device after the pump (`HYDRO_xxxx`) instead of the
    list label with MAC and signal strength;
  - refuses a gateway already used by another pump and a pump already
    configured, before writing anything to the gateway;
  - requires the gateway to be added to the ESPHome integration (also when
    its address is entered manually) and finds its entities by name, even if
    their entity IDs were renamed;
  - submitting the "no pumps found" form simply retries.
- The duplicate entities of the native ESPHome integration are disabled only
  once (an entity you re-enable stays enabled) and are re-enabled when this
  integration is removed.
- The connection to the gateway checks the ESPHome device name, so it never
  talks to another ESPHome device that took over the same IP address.
- Requires Home Assistant 2025.2 or newer (modern config-entry APIs; entities
  are push-updated, no polling).

### Removed

- *Estimated Water Level*, *Error Word*, *Status Word* and *Set Start
  Pressure* (the app never writes the start pressure: it equals target −
  delta).
- The zeroconf discovery rule, which could never match a gateway.
