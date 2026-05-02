# ha-philips-dline-sicp

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant custom integration to control **Philips D-Line** signage displays over your local network using the **SICP** binary protocol (TCP port 5000).

> Native HA equivalent of the [homebridge-philips-dline-sicp](https://github.com/Tomdazy/homebridge-philips-dline-sicp) Homebridge plugin.

---

## Features

| Feature | Details |
|---|---|
| **Power** | Turn on / standby |
| **Source selection** | HDMI 1–4, DisplayPort, VGA, Media Player, Browser, PDF Player… |
| **Volume** | Absolute level (0–100), mute/unmute, step up/down |
| **Brightness** | State attribute + `philips_dline_sicp.set_brightness` service |
| **Contrast** | State attribute + `philips_dline_sicp.set_contrast` service |
| **Polling** | Configurable interval (0 = disabled) |
| **Config Flow** | Full graphical setup — no YAML required |
| **Options Flow** | Edit settings any time without re-adding the integration |
| **Multi-display** | Add multiple entries for multiple monitors |

---

## Requirements

- Home Assistant **2024.1** or later
- A Philips D-Line display with network control enabled:
  - OSD menu → **Configuration 1 → Network Settings** → enable
  - Confirm the SICP port shows **5000 (Connected)**
  - Note the display **IP address** and **Monitor ID** (OSD → Advanced Option)
- The display must be reachable from HA on **TCP port 5000**

> ⚠️ The SICP protocol has no authentication. Keep your display on a trusted VLAN or local network segment.

---

## Installation

### Via HACS (recommended)

1. In HACS, click **Custom Repositories**
2. Add this repository URL with category **Integration**
3. Search for **"Philips D-Line SICP"** and click Install
4. Restart Home Assistant

### Manual

```bash
# From your HA config directory:
cp -r custom_components/philips_dline_sicp /config/custom_components/
```

Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Philips D-Line"**
3. Fill in the setup steps below

### Step 1 — Connection

| Field | Default | Description |
|---|---|---|
| IP address | — | Display IP on your LAN |
| TCP port | `5000` | SICP port (do not change unless needed) |
| Monitor ID | `1` | Display identifier from OSD → Advanced Option |
| Group ID | `0` | Group byte (usually 0) |
| Include Group byte | ✓ | Uncheck if you receive no ACK |

The integration will attempt a live connection before saving. If the display does not respond, an error is shown.

### Step 2 — Options

| Field | Default | Description |
|---|---|---|
| Poll interval | `15` s | How often to refresh state (0 = disabled) |
| Volume min | `0` | Lower bound for volume scaling |
| Volume max | `100` | Upper bound for volume scaling |
| Expose brightness | ✓ | Adds `brightness` to entity state attributes |
| Expose contrast | ✗ | Adds `contrast` to entity state attributes |

All options can be changed later via **Settings → Devices & Services → Configure** without removing the integration.

---

## Input Sources

Sources are defined in `const.py` (`DEFAULT_INPUTS`). SICP input codes may vary by firmware version — adjust if your display does not respond to a specific source.

| Source | SICP code |
|---|---|
| HDMI 1 | `0x0D` |
| HDMI 2 | `0x06` |
| HDMI 3 | `0x0F` |
| HDMI 4 | `0x19` |
| DisplayPort | `0x22` |
| DVI-D | `0x04` |
| VGA | `0x01` |
| Media Player | `0x30` |
| Browser | `0x40` |
| PDF Player | `0x41` |
| Card OPS | `0x07` |

---

## Services

### `philips_dline_sicp.set_brightness`

Set the display backlight brightness (0–100).

```yaml
service: philips_dline_sicp.set_brightness
data:
  brightness: 70
```

### `philips_dline_sicp.set_contrast`

Set the display contrast (0–100).

```yaml
service: philips_dline_sicp.set_contrast
data:
  contrast: 50
```

---

## Automation Examples

### Turn on at sunrise and select HDMI 1

```yaml
automation:
  - alias: "Living room display — morning on"
    trigger:
      platform: sun
      event: sunrise
    action:
      - service: media_player.turn_on
        target:
          entity_id: media_player.philips_d_line_192_168_1_120
      - delay: "00:00:02"
      - service: media_player.select_source
        target:
          entity_id: media_player.philips_d_line_192_168_1_120
        data:
          source: "HDMI 1"
```

### Dim the display at night

```yaml
automation:
  - alias: "Living room display — dim at night"
    trigger:
      platform: time
      at: "22:00:00"
    action:
      - service: philips_dline_sicp.set_brightness
        data:
          brightness: 20
```

### Mute on incoming call (example)

```yaml
automation:
  - alias: "Display mute during call"
    trigger:
      platform: state
      entity_id: binary_sensor.phone_in_call
      to: "on"
    action:
      - service: media_player.mute_volume
        target:
          entity_id: media_player.philips_d_line_192_168_1_120
        data:
          is_volume_muted: true
```

---

## Troubleshooting

| Symptom | Solution |
|---|---|
| "Cannot connect" during setup | Check IP, verify TCP port 5000 is reachable, confirm SICP is enabled in OSD |
| No ACK / repeated timeouts | Try disabling the Group byte (`Include Group byte = false`) |
| Source does not change | Your firmware may use different codes — cross-reference your SICP documentation |
| Entity becomes unavailable | Display is off or unreachable; state will recover on next poll when the display is back |

Quick connectivity test from a terminal:

```bash
nc -zv 192.168.1.120 5000
```

Enable debug logging for more detail:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.philips_dline_sicp: debug
```

---

## SICP Protocol Notes

SICP (Serial/Ethernet Interface Communication Protocol) is a binary framing protocol used across Philips professional displays. Each packet contains a length byte, monitor ID, optional group ID, a command byte, optional data bytes, and an XOR checksum. The display replies with ACK (success), NACK (checksum error), or NAV (command not supported by this firmware).

This integration uses **SICP v2** framing over TCP. If your display reports SICP v1.x, try disabling the Group byte in the options.

---

## License

MIT — see [LICENSE](LICENSE)
