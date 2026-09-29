"""Catalogue déclaratif des commandes SICP exposées en entités.

Chaque description associe une commande Get (lecture) et une commande Set
(écriture) de la spécification SICP 2.09. Les entités de niche, ou que peu
de modèles supportent, sont désactivées par défaut : on les active depuis
la fiche de l'appareil dans Home Assistant.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.button import ButtonDeviceClass, ButtonEntityDescription
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.time import TimeEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)

from .const import SOURCES
from .coordinator import (
    Q_ANDROID_FW,
    Q_BUILD_DATE,
    Q_FIRMWARE,
    Q_MODEL,
    Q_PLATFORM,
    Q_PLATFORM_VER,
    Q_SERIAL,
    Q_SICP_VERSION,
    TIER_FAST,
    TIER_SLOW,
    TIER_STATIC,
)

CONFIG = EntityCategory.CONFIG
DIAG = EntityCategory.DIAGNOSTIC


def frame_with(
    current: bytes | None, length: int | None, fill: int, index: int, value: int
) -> bytes:
    """Construit les données d'un Set à partir de la dernière lecture.

    length=None : un seul octet. Sinon, on recopie la trame lue (complétée
    par `fill`) et on remplace l'octet `index`.
    """
    if length is None:
        return bytes([value & 0xFF])
    base = bytearray((current or b"")[:length])
    base.extend([fill] * (length - len(base)))
    base[index] = value & 0xFF
    return bytes(base)


@dataclass(frozen=True, kw_only=True)
class SICPMixin:
    """Champs communs : où lire, où écrire."""

    get_cmd: int
    get_data: bytes = b""
    set_cmd: int | None = None
    index: int = 0
    # Longueur de la trame Set quand elle regroupe plusieurs paramètres
    frame_len: int | None = None
    # Valeur de remplissage si la trame courante est inconnue (0xFF = inchangé)
    fill: int = 0x00
    tier: str = TIER_SLOW
    available_when_off: bool = True

    @property
    def query(self) -> tuple[int, bytes]:
        return (self.get_cmd, self.get_data)


# ════════════════════════════════════════════════════════════
# Number
# ════════════════════════════════════════════════════════════

@dataclass(frozen=True, kw_only=True)
class PhilipsNumberDescription(NumberEntityDescription, SICPMixin):
    scale: int = 1


def _video(key: str, index: int, icon: str, enabled: bool = True) -> PhilipsNumberDescription:
    return PhilipsNumberDescription(
        key=key, translation_key=key, icon=icon,
        get_cmd=0x33, set_cmd=0x32, index=index, frame_len=7, fill=0xFF,
        tier=TIER_FAST,
        native_min_value=0, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE, mode=NumberMode.SLIDER,
        entity_registry_enabled_default=enabled,
    )


def _rgb(key: str, index: int) -> PhilipsNumberDescription:
    return PhilipsNumberDescription(
        key=key, translation_key=key, icon="mdi:palette",
        get_cmd=0x37, set_cmd=0x36, index=index, frame_len=6,
        native_min_value=0, native_max_value=255, native_step=1,
        mode=NumberMode.SLIDER, entity_category=CONFIG,
        entity_registry_enabled_default=False,
    )


def _limit(key: str, get_cmd: int, set_cmd: int, index: int) -> PhilipsNumberDescription:
    return PhilipsNumberDescription(
        key=key, translation_key=key, icon="mdi:volume-equal",
        get_cmd=get_cmd, set_cmd=set_cmd, index=index, frame_len=3,
        native_min_value=0, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE, entity_category=CONFIG,
        entity_registry_enabled_default=False,
    )


NUMBERS: tuple[PhilipsNumberDescription, ...] = (
    _video("brightness", 0, "mdi:brightness-6"),
    _video("color", 1, "mdi:palette"),
    _video("contrast", 2, "mdi:contrast-box"),
    _video("sharpness", 3, "mdi:image-filter-center-focus"),
    _video("tint", 4, "mdi:palette-swatch", enabled=False),
    _video("black_level", 5, "mdi:brightness-4", enabled=False),
    PhilipsNumberDescription(
        key="audio_out_volume", translation_key="audio_out_volume", icon="mdi:speaker-wireless",
        get_cmd=0x45, set_cmd=0x44, index=1, frame_len=2, fill=0xFF, tier=TIER_FAST,
        native_min_value=0, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE, mode=NumberMode.SLIDER,
        entity_registry_enabled_default=False,
    ),
    PhilipsNumberDescription(
        key="treble", translation_key="treble", icon="mdi:tune-vertical",
        get_cmd=0x43, set_cmd=0x42, index=0, frame_len=2,
        native_min_value=0, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE, entity_registry_enabled_default=False,
    ),
    PhilipsNumberDescription(
        key="bass", translation_key="bass", icon="mdi:tune-vertical",
        get_cmd=0x43, set_cmd=0x42, index=1, frame_len=2,
        native_min_value=0, native_max_value=100, native_step=1,
        native_unit_of_measurement=PERCENTAGE, entity_registry_enabled_default=False,
    ),
    PhilipsNumberDescription(
        key="color_temperature_kelvin", translation_key="color_temperature_kelvin",
        icon="mdi:thermometer-lines",
        get_cmd=0x12, set_cmd=0x11, scale=100,
        native_min_value=2000, native_max_value=10000, native_step=100,
        native_unit_of_measurement="K", mode=NumberMode.SLIDER,
        entity_registry_enabled_default=False,
    ),
    _rgb("red_gain", 0), _rgb("green_gain", 1), _rgb("blue_gain", 2),
    _rgb("red_offset", 3), _rgb("green_offset", 4), _rgb("blue_offset", 5),
    _limit("speaker_volume_min", 0xB6, 0xB8, 0),
    _limit("speaker_volume_max", 0xB6, 0xB8, 1),
    _limit("speaker_volume_power_on", 0xB6, 0xB8, 2),
    _limit("audio_out_volume_min", 0xB7, 0xB9, 0),
    _limit("audio_out_volume_max", 0xB7, 0xB9, 1),
    _limit("audio_out_volume_power_on", 0xB7, 0xB9, 2),
    PhilipsNumberDescription(
        key="information_osd", translation_key="information_osd", icon="mdi:information-outline",
        get_cmd=0x2D, set_cmd=0x2C,
        native_min_value=0, native_max_value=60, native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS, entity_category=CONFIG,
        entity_registry_enabled_default=False,
    ),
    PhilipsNumberDescription(
        key="off_timer", translation_key="off_timer", icon="mdi:timer-off-outline",
        get_cmd=0x91, set_cmd=0x92,
        native_min_value=0, native_max_value=24, native_step=1,
        native_unit_of_measurement=UnitOfTime.HOURS, entity_category=CONFIG,
    ),
    PhilipsNumberDescription(
        key="switch_on_delay", translation_key="switch_on_delay", icon="mdi:timer-sand",
        get_cmd=0x55, set_cmd=0x54,
        native_min_value=0, native_max_value=255, native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS, entity_category=CONFIG,
        entity_registry_enabled_default=False,
    ),
)


# ════════════════════════════════════════════════════════════
# Select
# ════════════════════════════════════════════════════════════

@dataclass(frozen=True, kw_only=True)
class PhilipsSelectDescription(SelectEntityDescription, SICPMixin):
    # code SICP → option
    values: dict[int, str] = field(default_factory=dict)
    # Masque appliqué à l'octet lu (0x3B : seuls les bits 3..0 comptent)
    mask: int = 0xFF
    # Trames Set complètes par option, quand l'index seul ne suffit pas
    frames: dict[str, bytes] | None = None


def _select(
    key: str, get_cmd: int, set_cmd: int, values: dict[int, str], icon: str,
    enabled: bool = True, category: EntityCategory | None = CONFIG, **kwargs,
) -> PhilipsSelectDescription:
    return PhilipsSelectDescription(
        key=key, translation_key=key, icon=icon,
        get_cmd=get_cmd, set_cmd=set_cmd, values=values, options=list(values.values()),
        entity_category=category, entity_registry_enabled_default=enabled, **kwargs,
    )


PIXEL_SHIFT = {0x00: "off", **{n: str(n * 10) for n in range(1, 0x5B)}, 0x5B: "auto"}

LANGUAGES = {
    0x01: "en_us", 0x02: "es_es", 0x03: "fr_fr", 0x04: "it_it", 0x05: "lv_lv",
    0x06: "lt_lt", 0x07: "nl_nl", 0x08: "nb_no", 0x09: "pl_pl", 0x0A: "pt_pt",
    0x0B: "fi_fi", 0x0C: "sv_se", 0x0D: "tr_tr", 0x0E: "ru_ru", 0x0F: "ar_eg",
    0x10: "zh_cn", 0x11: "zh_tw", 0x12: "ja_jp", 0x13: "cs_cz", 0x14: "da_dk",
    0x15: "de_de", 0x16: "et_ee",
}

TIME_ZONES = dict(enumerate([
    "Pacific/Midway", "Pacific/Honolulu", "America/Anchorage", "America/Los_Angeles",
    "America/Tijuana", "America/Phoenix", "America/Chihuahua", "America/Denver",
    "America/Costa_Rica", "America/Chicago", "America/Mexico_City", "America/Regina",
    "America/Bogota", "America/New_York", "America/Caracas", "America/Barbados",
    "America/Halifax", "America/Manaus", "America/Santiago", "America/St_Johns",
    "America/Sao_Paulo", "America/Argentina/Buenos_Aires", "America/Godthab",
    "America/Montevideo", "Atlantic/South_Georgia", "Atlantic/Azores",
    "Atlantic/Cape_Verde", "Africa/Casablanca", "Europe/London", "Europe/Amsterdam",
    "Europe/Belgrade", "Europe/Brussels", "Europe/Sarajevo", "Africa/Windhoek",
    "Africa/Brazzaville", "Asia/Amman", "Europe/Athens", "Asia/Beirut", "Africa/Cairo",
    "Europe/Helsinki", "Asia/Jerusalem", "Africa/Harare", "Europe/Minsk", "Asia/Baghdad",
    "Europe/Moscow", "Asia/Kuwait", "Africa/Nairobi", "Asia/Tehran", "Asia/Baku",
    "Asia/Tbilisi", "Asia/Yerevan", "Asia/Dubai", "Asia/Kabul", "Asia/Karachi",
    "Asia/Oral", "Asia/Yekaterinburg", "Asia/Calcutta", "Asia/Colombo", "Asia/Katmandu",
    "Asia/Almaty", "Asia/Rangoon", "Asia/Krasnoyarsk", "Asia/Bangkok", "Asia/Jakarta",
    "Asia/Shanghai", "Asia/Hong_Kong", "Asia/Irkutsk", "Asia/Kuala_Lumpur",
    "Australia/Perth", "Asia/Taipei", "Asia/Seoul", "Asia/Tokyo", "Asia/Yakutsk",
    "Australia/Adelaide", "Australia/Darwin", "Australia/Brisbane", "Australia/Hobart",
    "Australia/Sydney", "Asia/Vladivostok", "Pacific/Guam", "Asia/Magadan",
    "Pacific/Majuro", "Pacific/Auckland", "Pacific/Fiji", "Pacific/Tongatapu",
], start=1))

BOOT_SOURCES = {0x00: "Last input", **SOURCES}

SELECTS: tuple[PhilipsSelectDescription, ...] = (
    _select("picture_format", 0x3B, 0x3A, {
        0x00: "normal", 0x01: "custom", 0x02: "real", 0x03: "full",
        0x04: "wide_21_9", 0x05: "dynamic", 0x06: "wide_16_9",
    }, "mdi:aspect-ratio", category=None, mask=0x0F),
    _select("picture_style", 0x65, 0x66, {
        0x00: "highbright", 0x01: "srgb", 0x02: "vivid", 0x03: "natural",
        0x04: "standard", 0x05: "video", 0x06: "static_signage", 0x07: "text",
        0x08: "energy_saving", 0x09: "soft", 0x0A: "user",
    }, "mdi:image-edit", category=None),
    _select("gamma", 0x33, 0x32, {
        0x01: "native", 0x02: "s_gamma", 0x03: "gamma_2_2", 0x04: "gamma_2_4", 0x05: "dicom",
    }, "mdi:gamma", index=6, frame_len=7, fill=0xFF, tier=TIER_FAST),
    _select("color_temperature", 0x35, 0x34, {
        0x00: "user_1", 0x01: "native", 0x02: "k11000", 0x03: "k10000", 0x04: "k9300",
        0x05: "k7500", 0x06: "k6500", 0x07: "k5770", 0x08: "k5500", 0x09: "k5000",
        0x0A: "k4000", 0x0B: "k3400", 0x0C: "k3350", 0x0D: "k3000", 0x0E: "k2800",
        0x0F: "k2600", 0x10: "k1850", 0x12: "user_2",
    }, "mdi:thermometer", category=None),
    _select("noise_reduction", 0x2B, 0x2A, {
        0x00: "off", 0x01: "low", 0x02: "medium", 0x03: "high", 0x04: "default",
    }, "mdi:blur", enabled=False),
    _select("memc", 0x29, 0x28, {
        0x00: "off", 0x01: "low", 0x02: "medium", 0x03: "high",
    }, "mdi:motion-play-outline", enabled=False),
    _select("scan_mode", 0x51, 0x50, {
        0x00: "overscan", 0x01: "underscan", 0x02: "off",
    }, "mdi:fit-to-screen-outline", enabled=False),
    _select("scan_conversion", 0x53, 0x52, {
        0x00: "progressive", 0x01: "interlace",
    }, "mdi:view-sequential", enabled=False),
    _select("hdmi_range", 0x6A, 0x6B, {
        0x01: "auto", 0x02: "limited", 0x03: "full",
    }, "mdi:hdmi-port", enabled=False),
    _select("test_pattern", 0x6C, 0x6D, {
        0x00: "off", 0x01: "white", 0x02: "red", 0x03: "green", 0x04: "blue",
        0x05: "black", 0x06: "half_white_top", 0x07: "half_white_bottom", 0x08: "ramp",
        0x09: "white_12", 0x0A: "white_25", 0x0B: "white_65",
    }, "mdi:checkerboard", enabled=False),
    _select("factory_color_calibration", 0x31, 0x30, {
        0x00: "off", 0x01: "locked", 0x02: "adjustable",
    }, "mdi:palette-advanced", enabled=False),
    _select("orientation", 0x16, 0x17, {
        0x00: "landscape", 0x01: "portrait",
    }, "mdi:phone-rotate-landscape", index=1, enabled=False, frames={
        "landscape": bytes([0, 0, 0, 0, 0, 0, 0]),
        "portrait":  bytes([0, 1, 1, 1, 0, 0, 0]),
    }),
    _select("power_on_state", 0xA4, 0xA3, {
        0x00: "off", 0x01: "forced_on", 0x02: "last_status",
    }, "mdi:power-settings"),
    _select("boot_source", 0xBA, 0xBB, BOOT_SOURCES, "mdi:import",
            frame_len=2, enabled=False),
    _select("auto_signal_detection", 0xAF, 0xAE, {
        0x00: "off", 0x01: "all", 0x03: "pc_only", 0x04: "video_only", 0x05: "failover",
    }, "mdi:video-input-hdmi"),
    _select("smart_power", 0xDE, 0xDD, {
        0x00: "off", 0x01: "low", 0x02: "medium", 0x03: "high",
    }, "mdi:leaf"),
    _select("power_save_mode", 0xD3, 0xD2, {
        0x00: "rgb_off_video_off", 0x01: "rgb_off_video_on", 0x02: "rgb_on_video_off",
        0x03: "rgb_on_video_on", 0x04: "mode_1", 0x05: "mode_2", 0x06: "mode_3",
        0x07: "mode_4",
    }, "mdi:power-sleep", enabled=False),
    _select("apm", 0xD1, 0xD0, {
        0x00: "off", 0x01: "on", 0x02: "mode_1", 0x03: "mode_2",
    }, "mdi:lan-connect", enabled=False),
    _select("eco_mode", 0x63, 0x64, {
        0x00: "low_power_standby", 0x01: "normal",
    }, "mdi:sprout"),
    _select("pixel_shift", 0xB1, 0xB2, PIXEL_SHIFT, "mdi:arrow-all", enabled=False),
    _select("human_sensor", 0xB3, 0xB4, {
        0x00: "off", 0x01: "10", 0x02: "20", 0x03: "30", 0x04: "40", 0x05: "50", 0x06: "60",
    }, "mdi:motion-sensor", enabled=False),
    _select("fan_speed", 0x62, 0x61, {
        0x00: "off", 0x01: "auto", 0x02: "low", 0x03: "medium", 0x04: "high",
    }, "mdi:fan", enabled=False),
    _select("power_on_logo", 0x3F, 0x3E, {
        0x00: "off", 0x01: "on", 0x02: "user",
    }, "mdi:image-frame", enabled=False),
    _select("ir_lock", 0x1D, 0x1C, {
        0x01: "unlock_all", 0x02: "lock_all", 0x03: "lock_all_but_power",
        0x04: "lock_all_but_volume", 0x05: "primary", 0x06: "secondary",
        0x07: "lock_all_but_power_volume",
    }, "mdi:remote-off"),
    _select("keypad_lock", 0x1B, 0x1A, {
        0x01: "unlock_all", 0x02: "lock_all", 0x03: "lock_all_but_power",
        0x04: "lock_all_but_volume", 0x07: "lock_all_but_power_volume",
    }, "mdi:gesture-tap-button"),
    _select("touch", 0x1F, 0x1E, {
        0x01: "unlocked", 0x00: "locked", 0x10: "locked_silent",
    }, "mdi:gesture-tap", enabled=False),
    _select("navigation_bar", 0x74, 0x75, {
        0x00: "always_off", 0x01: "always_on", 0x02: "auto_hide",
    }, "mdi:dock-bottom", enabled=False),
    _select("hdmi_cec", 0xBC, 0xBD, {
        0x00: "off", 0x01: "on", 0x11: "on_with_power_off",
    }, "mdi:link-variant"),
    _select("ops_power", 0x6E, 0x6F, {
        0x00: "always_off", 0x01: "always_on", 0x02: "auto",
    }, "mdi:expansion-card", enabled=False),
    _select("rs232_routing", 0x9A, 0x9B, {
        0x00: "rs232", 0x01: "lan_rs232", 0x02: "card_ops_rs232",
    }, "mdi:serial-port", enabled=False),
    _select("language", 0xA7, 0xA8, LANGUAGES, "mdi:translate", enabled=False),
    _select("time_zone", 0x8B, 0x8A, TIME_ZONES, "mdi:earth", enabled=False),
)


# ════════════════════════════════════════════════════════════
# Switch
# ════════════════════════════════════════════════════════════

@dataclass(frozen=True, kw_only=True)
class PhilipsSwitchDescription(SwitchEntityDescription, SICPMixin):
    on_value: int = 0x01
    off_value: int = 0x00


def _switch(
    key: str, get_cmd: int, set_cmd: int, icon: str, enabled: bool = True,
    category: EntityCategory | None = CONFIG, **kwargs,
) -> PhilipsSwitchDescription:
    return PhilipsSwitchDescription(
        key=key, translation_key=key, icon=icon, get_cmd=get_cmd, set_cmd=set_cmd,
        entity_category=category, entity_registry_enabled_default=enabled, **kwargs,
    )


SWITCHES: tuple[PhilipsSwitchDescription, ...] = (
    _switch("freeze", 0x76, 0x77, "mdi:snowflake", category=None, tier=TIER_FAST),
    _switch("av_mute", 0x7A, 0x7B, "mdi:television-off", category=None, tier=TIER_FAST),
    _switch("speakers", 0x8F, 0x8E, "mdi:speaker", category=None),
    _switch("audio_sync", 0x8D, 0x8C, "mdi:sync", enabled=False),
    _switch("light_sensor", 0x25, 0x24, "mdi:brightness-auto", enabled=False),
    _switch("osd_rotation", 0x27, 0x26, "mdi:screen-rotation", enabled=False),
    _switch("power_led", 0x48, 0x49, "mdi:led-on"),
    _switch("wake_on_lan", 0x9C, 0x9D, "mdi:lan-pending"),
    _switch("auto_time_sync", 0x89, 0x88, "mdi:clock-check-outline", enabled=False),
    _switch("teamviewer", 0x93, 0x94, "mdi:remote-desktop", enabled=False),
    _switch("force_restart_app", 0x78, 0x79, "mdi:restart", enabled=False),
    _switch("external_storage_lock", 0xF2, 0xF1, "mdi:usb-flash-drive-outline"),
    _switch("auto_restart", 0x9E, 0x9F, "mdi:restart-alert", enabled=False, frame_len=3),
)


# ════════════════════════════════════════════════════════════
# Time
# ════════════════════════════════════════════════════════════

@dataclass(frozen=True, kw_only=True)
class PhilipsTimeDescription(TimeEntityDescription, SICPMixin):
    hour_index: int = 0
    frame_len: int | None = 2


TIMES: tuple[PhilipsTimeDescription, ...] = (
    PhilipsTimeDescription(
        key="auto_restart_time", translation_key="auto_restart_time", icon="mdi:clock-outline",
        get_cmd=0x9E, set_cmd=0x9F, hour_index=1, frame_len=3,
        entity_category=CONFIG, entity_registry_enabled_default=False,
    ),
    PhilipsTimeDescription(
        key="clock", translation_key="clock", icon="mdi:clock-digital",
        get_cmd=0x87, set_cmd=0x86, hour_index=0, frame_len=2,
        entity_category=CONFIG, entity_registry_enabled_default=False,
    ),
)


# ════════════════════════════════════════════════════════════
# Sensor / binary sensor
# ════════════════════════════════════════════════════════════

def _text(payload: bytes) -> str | None:
    text = payload.decode("ascii", errors="ignore").strip("\x00 ").strip()
    return text or None


@dataclass(frozen=True, kw_only=True)
class PhilipsSensorDescription(SensorEntityDescription, SICPMixin):
    value_fn: Callable[[bytes], object] = lambda p: p[0] if p else None


def _info(key: str, query: tuple[int, bytes], icon: str, enabled: bool = True) -> PhilipsSensorDescription:
    return PhilipsSensorDescription(
        key=key, translation_key=key, icon=icon,
        get_cmd=query[0], get_data=query[1], tier=TIER_STATIC,
        value_fn=_text, entity_category=DIAG, entity_registry_enabled_default=enabled,
    )


SENSORS: tuple[PhilipsSensorDescription, ...] = (
    PhilipsSensorDescription(
        key="temperature", translation_key="temperature",
        get_cmd=0x2F, device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=DIAG, available_when_off=False,
    ),
    PhilipsSensorDescription(
        key="operating_hours", translation_key="operating_hours", icon="mdi:timer-outline",
        get_cmd=0x0F, get_data=b"\x02",
        value_fn=lambda p: (p[0] << 8 | p[1]) if len(p) >= 2 else None,
        device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS, entity_category=DIAG,
    ),
    _info("model", Q_MODEL, "mdi:monitor"),
    _info("firmware_version", Q_FIRMWARE, "mdi:chip"),
    _info("android_version", Q_ANDROID_FW, "mdi:android"),
    _info("build_date", Q_BUILD_DATE, "mdi:calendar", enabled=False),
    _info("sicp_version", Q_SICP_VERSION, "mdi:protocol"),
    _info("platform", Q_PLATFORM, "mdi:developer-board", enabled=False),
    _info("platform_version", Q_PLATFORM_VER, "mdi:developer-board", enabled=False),
    _info("serial_number", Q_SERIAL, "mdi:barcode"),
    _info("hdmi_switch_version", (0xA1, b"\x04"), "mdi:hdmi-port", enabled=False),
    _info("lan_firmware_version", (0xA1, b"\x05"), "mdi:lan", enabled=False),
)


@dataclass(frozen=True, kw_only=True)
class PhilipsBinarySensorDescription(BinarySensorEntityDescription, SICPMixin):
    on_value: int = 0x01


BINARY_SENSORS: tuple[PhilipsBinarySensorDescription, ...] = (
    PhilipsBinarySensorDescription(
        key="video_signal", translation_key="video_signal", icon="mdi:video-input-hdmi",
        get_cmd=0x59, tier=TIER_FAST, available_when_off=False,
    ),
)


# ════════════════════════════════════════════════════════════
# Button
# ════════════════════════════════════════════════════════════

@dataclass(frozen=True, kw_only=True)
class PhilipsButtonDescription(ButtonEntityDescription):
    cmd: int
    data: bytes = b""


BUTTONS: tuple[PhilipsButtonDescription, ...] = (
    PhilipsButtonDescription(
        key="restart", translation_key="restart", device_class=ButtonDeviceClass.RESTART,
        cmd=0x57, data=b"\x00", entity_category=CONFIG,
    ),
    PhilipsButtonDescription(
        key="screenshot", translation_key="screenshot", icon="mdi:monitor-screenshot",
        cmd=0x58, entity_registry_enabled_default=False,
    ),
    PhilipsButtonDescription(
        key="admin_menu", translation_key="admin_menu", icon="mdi:cog",
        cmd=0x73, entity_registry_enabled_default=False,
    ),
    PhilipsButtonDescription(
        key="vga_auto_adjust", translation_key="vga_auto_adjust", icon="mdi:auto-fix",
        cmd=0x70, data=b"\x40\x00", entity_category=CONFIG,
        entity_registry_enabled_default=False,
    ),
    PhilipsButtonDescription(
        key="channel_up", translation_key="channel_up", icon="mdi:chevron-up",
        cmd=0xC3, data=b"\x01", entity_registry_enabled_default=False,
    ),
    PhilipsButtonDescription(
        key="channel_down", translation_key="channel_down", icon="mdi:chevron-down",
        cmd=0xC3, data=b"\x00", entity_registry_enabled_default=False,
    ),
    PhilipsButtonDescription(
        key="reset_schedules", translation_key="reset_schedules", icon="mdi:calendar-remove",
        cmd=0x60, data=b"\x00", entity_category=CONFIG,
        entity_registry_enabled_default=False,
    ),
    PhilipsButtonDescription(
        key="factory_reset", translation_key="factory_reset", icon="mdi:factory",
        cmd=0x56, entity_category=CONFIG, entity_registry_enabled_default=False,
    ),
)
