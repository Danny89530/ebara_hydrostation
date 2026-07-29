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
You need that flashed and running before this integration is useful. Think
of it as: ESP32 + BLE = gateway, Home Assistant + this integration = the
nice dashboard on top.

## What you get

Once it's set up, you get a device in Home Assistant with:

- **Sensors**: actual/target/start/delta pressure, motor current, motor
  frequency, working hours, module temperature, DC bus voltage, estimated
  water level (derived from motor current), firmware/hardware version,
  serial and lot number, a decoded error-word (e.g. "Over-temperature",
  "Dry run", ...) and gateway connection status.
- **Binary sensors**: motor running / motor enabled / motor error.
- **Switches**: turn the motor on/off, and a "Gateway Enable" switch that
  lets you pause the ESP32's Bluetooth connection to the pump entirely
  without touching the ESP32 itself.
- **Numbers**: writable target/start/delta pressure setpoints, and the
  gateway's poll interval (how often it re-reads the pump over BLE).

Everything is grouped under one device named after your pump, with entity
names that actually make sense, instead of the raw names ESPHome itself
would expose.

## Why a separate integration instead of just using ESPHome's own device page

Home Assistant already has native support for any ESPHome device out of the
box — no extra integration needed for that. I built this on top of it anyway
because I wanted:

- One clean device with sensible names, instead of a long flat list of
  entities named after whatever I called them in the ESPHome YAML.
- A config flow that walks you through discovering nearby Hydrostation pumps
  over BLE and picking the right one, instead of you having to know its MAC
  address up front.
- Room to add pump-specific logic in Python (like decoding the error
  bitmask into readable text) without cramming it all into the ESP32
  firmware.

Under the hood it keeps its own connection to the ESP32 over the native
ESPHome API, and on setup it automatically disables the duplicate entities
the native ESPHome integration would otherwise also create for the same
device — the ESP32 stays visible for the few things this integration
doesn't replicate (its Target MAC input, the "Discovered Hydrostations"
list used during setup, and the reboot button), so you're never staring at
two copies of the same sensor.

## Requirements

- Home Assistant, recent enough to run config-flow integrations (nothing
  exotic — anything from the last couple of years should be fine).
- The [companion ESPHome gateway](https://github.com/Danny89530/esphome-ebara-hydrostation),
  already flashed onto an ESP32 and connected to your WiFi, with its native
  ESPHome integration already added to Home Assistant (or reachable on your
  network — the config flow can also take a host/port manually).
- An Ebara Hydrostation pump within Bluetooth range of that ESP32.

## Installation

### Via HACS (recommended)

1. In HACS, go to **Integrations** → the three-dot menu → **Custom
   repositories**.
2. Add this repository's URL, category **Integration**.
3. Find "Ebara Hydrostation" in HACS and install it.
4. Restart Home Assistant.

### Manual install

Copy the `custom_components/ebara_hydrostation` folder from this repository
into your Home Assistant `config/custom_components/` directory, then
restart Home Assistant.

## Configuration

Everything is done through the UI, no YAML required:

1. **Settings → Devices & Services → Add Integration → "Ebara Hydrostation"**.
2. If you already have the ESPHome gateway added natively, it'll be
   detected automatically — pick it from the list. Otherwise, enter its
   host/port yourself.
3. The gateway scans for nearby pumps and lists whatever it finds
   (name, MAC address, signal strength). Pick yours.
4. Done — the device and its entities show up right away.

If you ever need to point it at a different pump, or the pump's MAC
changes for some reason, just remove and re-add the integration; the target
MAC is stored on the ESP32 itself, so it survives Home Assistant restarts
either way.

## A couple of things worth knowing

- The poll interval is configurable (5–300 seconds) from the "Update
  Interval" entity — lower means fresher data but more BLE traffic to the
  pump; the default (15s) is a reasonable middle ground.
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
