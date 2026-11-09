# Ebara Hydrostation for Home Assistant

A custom Home Assistant integration for the **Ebara Hydrostation**, a
constant-pressure water pump that only talks Bluetooth Low Energy to its
official Android app. There's no official local API, no cloud API, nothing
— so I reverse-engineered the BLE protocol and built this to get the pump
properly into Home Assistant, with clean entities and a useful set of
controls instead of nothing at all.

This integration doesn't talk to the pump directly. It talks to a companion
ESP32 gateway running a custom [ESPHome](https://esphome.io) component that
does the actual Bluetooth work — see
**[ebara-hydrostation-esphome](https://github.com/Danny89530/esphome-ebara-hydrostation)**.
You need that flashed and running before this integration is useful, and
the two must be on matching major versions (integration 2.x ↔ gateway
component 2.x). Think
of it as: ESP32 + BLE = gateway, Home Assistant + this integration = the
nice dashboard on top.

## What you get

Once it's set up, you get a device in Home Assistant with:

- **Sensors**: actual/target/start/restart-delta pressure (always in bar),
  motor current, raw motor frequency, estimated pump load (the app's
  "FREQUENCY SPEED" %, derived from motor current), working hours, module
  temperature, DC bus voltage, pump status (Running, Standby, Assist mode,
  External stop, Alarm, Pump off, Offline), pressure unit configured on the
  pump, pump Bluetooth name, firmware/hardware version, serial number and
  gateway status.
- **Active alarms**: the alarm codes the pump reports (E01…E06, H01, H01+,
  H02, C01) with the official app's texts in English or Italian; each
  alarm's severity and suggested remedy are available as attributes.
- **Binary sensors**: motor running, motor enabled, pump alarm, external
  stop, and a diagnostic raw status bit not decoded by the app.
- **Switches**: the pump's automatic control on/off (refused by the gateway
  while an alarm is active, as in the app), and a "Gateway enable" switch
  that pauses the ESP32's Bluetooth connection to the pump entirely.
- **Numbers**: writable target pressure (2.0–5.5 bar) and restart delta
  (0.5–2.0 bar), and the gateway's update interval for live values.

Everything is grouped under one device named after your pump, with entity
names translated into English or Italian, and the pump's firmware/hardware
version and serial number shown on the device page. When the pump is
unreachable its values are shown as unknown, never as stale readings.

## Why a separate integration instead of just using ESPHome's own device page

Home Assistant already has native support for any ESPHome device out of the
box — no extra integration needed for that. I built this on top of it anyway
because I wanted:

- One clean device with sensible names, instead of a long flat list of
  entities named after whatever I called them in the ESPHome YAML.
- A config flow that walks you through discovering nearby Hydrostation pumps
  over BLE and picking the right one, instead of you having to know its MAC
  address up front.
- Room for pump-specific logic in Python (like translating the alarm codes
  and attaching the remedies) without cramming it all into the ESP32
  firmware.

Under the hood it keeps its own connection to the ESP32 over the native
ESPHome API, and on setup it automatically disables the duplicate entities
the native ESPHome integration would otherwise also create for the same
device — once, so if you deliberately re-enable one of them it stays
enabled. The ESP32 stays visible for the few things this integration
doesn't replicate (its Target MAC input, the "Discovered Hydrostations"
list used during setup, and the reboot button), so you're never staring at
two copies of the same sensor. Removing the integration re-enables them.

## Requirements

- Home Assistant 2025.2 or newer (tested on 2026.11).
- The [companion ESPHome gateway](https://github.com/Danny89530/esphome-ebara-hydrostation),
  version 2.x, flashed onto an ESP32 and connected to your WiFi, **with its
  device already added to Home Assistant's ESPHome integration** — the setup
  wizard reads the list of discovered pumps through it.
- An Ebara Hydrostation pump of the **HYDRO** family within Bluetooth range
  of that ESP32. HYSTA pumps use a different protocol and are not supported
  (the wizard does not list them).

## Installation

### Via the Marketplace / HACS (recommended)

On Home Assistant 2026.11 and newer, HACS content lives in the built-in
**Marketplace**; on older versions use HACS. Either way:

1. Add this repository's URL as a custom repository, category
   **Integration**.
2. Find "Ebara Hydrostation" and install it.
3. Restart Home Assistant.

New releases are then offered as updates automatically.

### Manual install

Copy the `custom_components/ebara_hydrostation` folder from this repository
into your Home Assistant `config/custom_components/` directory, then
restart Home Assistant.

## Configuration

Everything is done through the UI, no YAML required:

1. **Settings → Devices & Services → Add Integration → "Ebara Hydrostation"**.
2. The gateway is detected from your ESPHome devices — pick it from the
   list. If it isn't listed, you can enter its address, but it must still
   be added to the ESPHome integration first.
3. The gateway scans for nearby pumps and lists whatever it finds
   (name, MAC address, signal strength). Pick yours. If the list is empty,
   check the pump and submit again to retry.
4. Done — the device and its entities show up right away.

One gateway drives one pump: a gateway already in use is refused. To point
it at a different pump, remove and re-add the integration; the target MAC is
stored on the ESP32 itself, so it survives Home Assistant restarts either
way.

## Upgrading from 1.x

The update keeps your existing entry, entity IDs and history: the obsolete
entities (estimated water level, error word, status word, start-pressure
setpoint) are removed automatically and the new ones are added. Update the
**ESPHome gateway** too (see its changelog): until it runs component 2.x
with the new entities in its YAML, Home Assistant shows a repair notice and
the new entities stay unknown. Details in [CHANGELOG.md](CHANGELOG.md).

## A couple of things worth knowing

- The update interval for live values is configurable (2–300 seconds) from
  the "Update interval" entity and applies immediately; slow-changing values
  (working hours, temperature, voltage) are read every 60 s regardless. The
  default comes from the gateway YAML (10 s).
- Pressure setpoints are exposed as writable slider entities, but I'd treat
  them with the same care you'd use in the official app — they change how
  your pump actually behaves.
- This is a reverse-engineered protocol, not an official one. I've been
  careful to only ship commands I could confirm actually work against real
  hardware, and to never guess at a wire format and try it live — see the
  ESPHome repo's documentation for the details on what's supported and what
  deliberately isn't (yet).

This project isn't affiliated with, endorsed by, or supported by Ebara in
any way. Use it at your own risk.
