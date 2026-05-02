"""Constants for the Philips D-Line SICP integration."""

DOMAIN = "philips_dline_sicp"
PLATFORMS = ["media_player"]

# Config entry keys
CONF_HOST          = "host"
CONF_PORT          = "port"
CONF_MONITOR_ID    = "monitor_id"
CONF_GROUP_ID      = "group_id"
CONF_INCLUDE_GROUP = "include_group"
CONF_POLL_INTERVAL = "poll_interval"
CONF_INPUTS        = "inputs"
CONF_INPUT_LABEL   = "label"
CONF_INPUT_CODE    = "code"
CONF_VOLUME_MIN    = "volume_min"
CONF_VOLUME_MAX    = "volume_max"
CONF_EXPOSE_BRIGHTNESS = "expose_brightness"
CONF_EXPOSE_CONTRAST   = "expose_contrast"

# Defaults
DEFAULT_PORT          = 5000
DEFAULT_MONITOR_ID    = 1
DEFAULT_GROUP_ID      = 0
DEFAULT_INCLUDE_GROUP = True
DEFAULT_POLL_INTERVAL = 15
DEFAULT_VOLUME_MIN    = 0
DEFAULT_VOLUME_MAX    = 100
DEFAULT_EXPOSE_BRIGHTNESS = True
DEFAULT_EXPOSE_CONTRAST   = False

# Default inputs (D-Line firmware)
DEFAULT_INPUTS = [
    {"label": "HDMI 1",       "code": "0x0D"},
    {"label": "HDMI 2",       "code": "0x06"},
    {"label": "HDMI 3",       "code": "0x0F"},
    {"label": "HDMI 4",       "code": "0x19"},
    {"label": "DisplayPort",  "code": "0x22"},
    {"label": "VGA",          "code": "0x01"},
    {"label": "Media Player", "code": "0x30"},
]
