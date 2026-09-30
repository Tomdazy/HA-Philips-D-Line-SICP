"""Constantes de l'intégration Philips D-Line SICP."""
from homeassistant.const import Platform

DOMAIN = "philips_dline_sicp"
PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.TIME,
]

# Clés de configuration
CONF_HOST          = "host"
CONF_PORT          = "port"
CONF_MONITOR_ID    = "monitor_id"
CONF_GROUP_ID      = "group_id"
CONF_INCLUDE_GROUP = "include_group"
CONF_POLL_INTERVAL = "poll_interval"
CONF_SLOW_POLL_INTERVAL = "slow_poll_interval"
CONF_SOURCES       = "sources"
CONF_VOLUME_MIN    = "volume_min"
CONF_VOLUME_MAX    = "volume_max"
CONF_VOLUME_STEP   = "volume_step"
CONF_MAC           = "mac"

# Valeurs par défaut
DEFAULT_PORT          = 5000
DEFAULT_MONITOR_ID    = 1
DEFAULT_GROUP_ID      = 0
DEFAULT_INCLUDE_GROUP = True
DEFAULT_POLL_INTERVAL = 15
DEFAULT_SLOW_POLL_INTERVAL = 300
DEFAULT_VOLUME_MIN    = 0
DEFAULT_VOLUME_MAX    = 100
DEFAULT_VOLUME_STEP   = 2

# Codes de source des commandes 0xAC / 0xAD / 0xBA / 0xBB / 0x5A (SICP 2.09 §4.4)
SOURCES: dict[int, str] = {
    0x01: "Video",
    0x02: "S-Video",
    0x03: "Component",
    0x05: "VGA",
    0x06: "HDMI 2",
    0x07: "DisplayPort 2",
    0x08: "USB 2",
    0x09: "Card DVI-D",
    0x0A: "DisplayPort",
    0x0B: "Card OPS",
    0x0C: "USB",
    0x0D: "HDMI 1",
    0x0E: "DVI-D",
    0x0F: "HDMI 3",
    0x10: "Browser",
    0x11: "SmartCMS",
    0x12: "DMS",
    0x13: "Internal Storage",
    0x16: "Media Player",
    0x17: "PDF Player",
    0x18: "Custom",
    0x19: "HDMI 4",
    0x1A: "VGA 2",
    0x1B: "VGA 3",
    0x1C: "IWB",
    0x1D: "CMND & Play Web",
    0x1E: "Home",
    0x1F: "USB-C",
    0x20: "Kiosk",
    0x21: "Smart Info",
    0x22: "Tuner",
    0x23: "Google Cast",
    0x24: "Interact",
}

# Sources proposées quand le moniteur ne sait pas lister les siennes (0xAB)
DEFAULT_SOURCES = [0x0D, 0x06, 0x0F, 0x19, 0x0A, 0x05, 0x16, 0x10, 0x17, 0x18]


def source_name(code: int) -> str:
    """Libellé d'une source, y compris pour un code inconnu."""
    return SOURCES.get(code, f"Source 0x{code:02X}")
