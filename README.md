# ha-philips-dline-sicp

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🇫🇷 [Version française](README.fr-FR.md)

Home Assistant integration to control **Philips professional displays** (D-Line and other Signage models) over the local network with the **SICP** protocol (TCP port 5000), following the SICP 2.09 specification.

The display shows up as a **television**: HomeKit Bridge exposes it in the Home app as a Television accessory, with power, inputs, volume and the iPhone remote.

---

## What you can control

Entities marked ◌ are **disabled by default**, because few models support them or they are rarely needed. Enable them from the device page (*Settings → Devices & services → Philips D-Line → hidden entities*).

| Platform | Entities |
|---|---|
| **Television** (`media_player`) | Power / standby, input source, speaker volume, mute |
| **Backlight** (`light`) | Turn the panel on or off without powering down the electronics, brightness. In HomeKit it is a dimmable bulb. |
| **Settings** (`number`) | Brightness, color, contrast, sharpness, tint ◌, black level ◌, audio out volume ◌, treble ◌, bass ◌, color temperature in kelvin ◌, RGB gains and offsets ◌, volume limits ◌, information OSD duration ◌, off timer, switch-on delay ◌ |
| **Modes** (`select`) | Picture format, picture style, gamma, color temperature, power-on state, auto signal detection, Smart power, ECO mode, HDMI CEC, remote control lock, keypad lock. Disabled by default: noise reduction, MEMC, scan mode, scan conversion, HDMI range, test pattern, factory color calibration, orientation, boot source, power saving mode, APM, pixel shift, human sensor, fan speed, power-on logo, touch, navigation bar, OPS/SDM power, network control port, OSD language, time zone |
| **Switches** (`switch`) | Freeze screen, A/V mute, internal speakers, power LED, Wake on LAN, USB / microSD lock. Disabled by default: audio sync, light sensor, OSD rotation, automatic time sync, TeamViewer, force restart custom app, auto restart |
| **Times** (`time`) | Auto restart time ◌, display clock ◌ |
| **Sensors** (`sensor`) | Temperature, operating hours, model, firmware version, Android firmware, SICP version, serial number. Disabled by default: build date, platform, HDMI switch and LAN firmware |
| **Binary sensor** | Video signal present |
| **Buttons** (`button`) | Restart. Disabled by default: screenshot by e-mail, Android admin menu, VGA auto adjust, channel +/−, reset schedules, factory reset |

A command your display does not know (NACK reply, or repeated NAV) makes the entity *unavailable*. The integration retries it one hour later.

The input list is read from the display (command `0xAB`, SICP 2.05+). Otherwise you pick inputs from the full catalogue.

---

## Requirements

- Home Assistant **2024.1** or later
- A Philips display with network control enabled:
  - OSD → **Configuration 1 → Network settings**: enable networking
  - check that the SICP port shows **5000**
  - note the **IP address** and **Monitor ID** (OSD → Advanced option)
- TCP port **5000** of the display reachable from Home Assistant
- For remote power-on, the display must keep its network active in standby: set **APM / ECO mode** accordingly (see the display manual)

> ⚠️ SICP has no authentication: keep the display on a trusted network.

---

## Installation

### HACS (recommended)

1. In HACS, open **Custom repositories**
2. Add this repository URL, category **Integration**
3. Install **Philips D-Line SICP**
4. Restart Home Assistant

### Manual

```bash
cp -r custom_components/philips_dline_sicp /config/custom_components/
```

Then restart Home Assistant.

---

## Configuration

*Settings → Devices & services → Add integration → Philips D-Line*

### Step 1: connection

| Field | Default | Purpose |
|---|---|---|
| IP address | — | Display IP |
| TCP port | `5000` | SICP port |
| Monitor ID | `1` | Identifier set in the OSD |
| Group ID | `0` | `0` = address by Monitor ID |
| Include the Group byte | ✓ | Untick only for very old firmware (SICP 1.x) |

The integration tests the connection before saving.

### Step 2: options (editable later with **Configure**)

| Field | Default | Purpose |
|---|---|---|
| Inputs | inputs reported by the display | Inputs offered in Home Assistant and HomeKit |
| State refresh interval | `15` s | Power, input, volume, picture (0 = disabled) |
| Settings refresh interval | `300` s | All other settings |
| Minimum / maximum volume | `0` / `100` | Volume slider bounds |
| Volume step | `2` | Increment of the volume + / − buttons |
| MAC address | detected | For Wake on LAN power-on; leave empty for auto-detection |

In standby only the power state is polled: the display rejects most other commands in that state.

---

## HomeKit: the display as a television

HomeKit only accepts televisions as **standalone accessories**, not behind a bridge. Home Assistant handles this for you:

1. *Settings → Devices & services → Add integration → **HomeKit Bridge***
2. Tick at least the **Media player** domain (add **Light** and **Switch** for brightness and switches), then submit
3. Home Assistant creates the bridge **plus a dedicated accessory-mode instance for the television**. Each one posts a pairing QR code in the notifications.
4. In the Home app: **Add accessory**, then scan the television's QR code (and the bridge's if you use it)

If HomeKit Bridge is already set up, add a HomeKit Bridge entry in **accessory mode** (options: *Mode* `accessory`, *Entity* `media_player.philips_…`).

In the Home app you then get:

- power on and standby
- the **inputs**, with their names (rename or hide them in the app)
- **volume** and **mute** from the Control Center remote, using the iPhone hardware buttons

Through the bridge, the **backlight** shows up as a dimmable bulb (screen brightness) and the **switches** (freeze screen, A/V mute…) as outlets. Filter the exposed entities in the bridge options.

> The iOS remote arrow keys have no SICP equivalent. Home Assistant still fires the `homekit_tv_remote_key_pressed` event, which you can use in automations.

---

## Actions

### `philips_dline_sicp.select_source_playlist`

Switches to Media Player, PDF Player or Browser and starts a playlist or URL (1 to 7, 8 = USB autoplay).

```yaml
action: philips_dline_sicp.select_source_playlist
target:
  entity_id: media_player.philips_43bdl4550d_00
data:
  source: Media Player
  playlist: 2
```

### `philips_dline_sicp.set_brightness` / `set_contrast`

Kept for compatibility. Prefer the matching `number` entities.

```yaml
action: philips_dline_sicp.set_brightness
target:
  entity_id: media_player.philips_43bdl4550d_00
data:
  brightness: 70
```

### `philips_dline_sicp.send_raw_command`

Diagnostics: sends a raw SICP command and **returns** the reply (in *Developer tools → Actions*, tick "Return response").

```yaml
action: philips_dline_sicp.send_raw_command
data:
  cmd: "0xA2"
  data: "00"
```

---

## Automation examples

### Turn on at 8 am on HDMI 1

```yaml
automation:
  - alias: Display morning power-on
    triggers:
      - trigger: time
        at: "08:00:00"
    actions:
      - action: media_player.turn_on
        target:
          entity_id: media_player.philips_43bdl4550d_00
      - delay: "00:00:05"
      - action: media_player.select_source
        target:
          entity_id: media_player.philips_43bdl4550d_00
        data:
          source: HDMI 1
```

### Dim the display in the evening

```yaml
automation:
  - alias: Display evening dimming
    triggers:
      - trigger: time
        at: "20:00:00"
    actions:
      - action: number.set_value
        target:
          entity_id: number.philips_43bdl4550d_00_brightness
        data:
          value: 30
```

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| "Cannot reach the display" | IP, port 5000 (`nc -zv <ip> 5000`) and network control in the OSD |
| Power-on does not work | Set APM / ECO mode so the network stays active in standby, and enable **Wake on LAN** on the display ("Wake on LAN" switch or OSD menu): when SICP no longer answers, the integration powers the screen on with a magic packet |
| The display does not answer at all in standby | Expected on some Android models (e.g. 55BDL4511D): the TV shows as "off" and powers back on through Wake on LAN. Check the MAC address in the options if auto-detection failed. |
| Random replies, lost commands | Only one program may drive the SICP port: disable any other controller (Homebridge plugin, Crestron, CMND…). The display sends its replies on the most recently opened connection. |
| An entity stays unavailable | Your model does not support that command. Disable the entity. |
| Picture settings unavailable on an Android source | Expected on some models (BDL3452T, BDL3651T, BDL3550Q, BDL4550D): SICP only adjusts the picture of external inputs there |
| No reply at all | Try unticking "Include the Group byte" (very old firmware) |

Debug logs:

```yaml
logger:
  logs:
    custom_components.philips_dline_sicp: debug
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Release history is in [CHANGELOG.md](CHANGELOG.md).

## License

MIT, see [LICENSE](LICENSE).
