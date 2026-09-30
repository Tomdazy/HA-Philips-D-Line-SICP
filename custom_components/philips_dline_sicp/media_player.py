"""Plateforme media_player : le moniteur vu comme une télévision.

device_class = TV : HomeKit Bridge l'expose en accessoire « Téléviseur »
(alimentation, entrées, volume et sourdine via la télécommande de l'iPhone).
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SOURCES,
    CONF_VOLUME_MAX,
    CONF_VOLUME_MIN,
    CONF_VOLUME_STEP,
    DEFAULT_SOURCES,
    DEFAULT_VOLUME_MAX,
    DEFAULT_VOLUME_MIN,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    SOURCES,
    source_name,
)
from .coordinator import TIER_FAST, PhilipsDLineCoordinator
from .entity import PhilipsDLineEntity, device_unique_id
from .sicp import (
    CMD_INPUT_GET,
    CMD_MUTE_GET,
    CMD_MUTE_SET,
    CMD_VIDEO_GET,
    CMD_VIDEO_SET,
    CMD_VOLUME_GET,
    SICPError,
)

_LOGGER = logging.getLogger(__name__)

Q_VOLUME = (CMD_VOLUME_GET, b"")
Q_MUTE   = (CMD_MUTE_GET, b"")
Q_SOURCE = (CMD_INPUT_GET, b"")
Q_VIDEO  = (CMD_VIDEO_GET, b"")

SERVICE_SELECT_PLAYLIST = "select_source_playlist"
SERVICE_SET_BRIGHTNESS  = "set_brightness"
SERVICE_SET_CONTRAST    = "set_contrast"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PhilipsDLineMediaPlayer(runtime["coordinator"], runtime["config"])])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SELECT_PLAYLIST,
        {
            vol.Required("source"): cv.string,
            vol.Optional("playlist", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
        },
        "async_select_source_playlist",
    )
    platform.async_register_entity_service(
        SERVICE_SET_BRIGHTNESS,
        {vol.Required("brightness"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100))},
        "async_set_brightness",
    )
    platform.async_register_entity_service(
        SERVICE_SET_CONTRAST,
        {vol.Required("contrast"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100))},
        "async_set_contrast",
    )


class PhilipsDLineMediaPlayer(PhilipsDLineEntity, MediaPlayerEntity):
    """Le moniteur Philips D-Line en tant que téléviseur."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(self, coordinator: PhilipsDLineCoordinator, config: dict) -> None:
        super().__init__(coordinator, config)
        # Identifiant historique conservé pour ne pas recréer l'entité
        self._attr_unique_id = device_unique_id(config)

        self._vol_min  = int(config.get(CONF_VOLUME_MIN, DEFAULT_VOLUME_MIN))
        self._vol_max  = int(config.get(CONF_VOLUME_MAX, DEFAULT_VOLUME_MAX))
        self._vol_step = int(config.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP))

        # Sources : choix de l'utilisateur, sinon celles annoncées par le moniteur
        codes = config.get(CONF_SOURCES) or coordinator.sources or DEFAULT_SOURCES
        self._source_map: dict[str, int] = {}
        for code in codes:
            code = int(code)
            self._source_map[source_name(code)] = code
        self._attr_source_list = list(self._source_map)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        for query in (Q_VOLUME, Q_MUTE, Q_SOURCE):
            self.async_on_remove(self.coordinator.register(query, TIER_FAST))

    # ──────────────────────────────────────────
    # État
    # ──────────────────────────────────────────

    @property
    def available(self) -> bool:
        # Toujours disponible : un moniteur muet est en veille, et HomeKit doit
        # pouvoir le rallumer (par Wake on LAN si le SICP ne répond plus).
        return True

    @property
    def state(self) -> MediaPlayerState:
        if self.coordinator.reachable and self.coordinator.power:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    def _payload(self, query) -> bytes | None:
        if self.state is MediaPlayerState.OFF:
            return None
        return self.coordinator.payload(query)

    @property
    def _speaker_volume(self) -> int | None:
        payload = self.coordinator.payload(Q_VOLUME)
        return payload[0] if payload else None

    @property
    def volume_level(self) -> float | None:
        raw = self._speaker_volume
        if raw is None:
            return None
        span = self._vol_max - self._vol_min
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (raw - self._vol_min) / span))

    @property
    def volume_step(self) -> float:
        span = self._vol_max - self._vol_min
        return self._vol_step / span if span > 0 else 0.02

    @property
    def is_volume_muted(self) -> bool | None:
        payload = self._payload(Q_MUTE)
        return payload[0] == 0x01 if payload else None

    @property
    def source(self) -> str | None:
        payload = self._payload(Q_SOURCE)
        if not payload:
            return None
        return source_name(payload[0])

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        source = self._payload(Q_SOURCE)
        if source and len(source) > 1 and source[0] in (0x10, 0x16, 0x17):
            attrs["playlist"] = source[1]
        volume = self._payload(Q_VOLUME)
        if volume and len(volume) > 1:
            attrs["audio_out_volume"] = volume[1]
        return attrs

    # ──────────────────────────────────────────
    # Commandes
    # ──────────────────────────────────────────

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_power(True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_power(False)

    async def _ensure_on(self) -> None:
        if self.state is MediaPlayerState.OFF:
            await self.coordinator.async_set_power(True)

    async def _set_speaker_volume(self, level: int) -> None:
        await self._ensure_on()
        level = max(self._vol_min, min(self._vol_max, level))
        try:
            await self.coordinator.client.async_set_volume(level)
        except SICPError as exc:
            raise ServiceValidationError(f"Réglage du volume refusé : {exc}") from exc
        await self.coordinator.async_refresh_queries([Q_VOLUME, Q_MUTE])

    async def async_set_volume_level(self, volume: float) -> None:
        span = self._vol_max - self._vol_min
        await self._set_speaker_volume(int(round(self._vol_min + volume * span)))

    async def async_volume_up(self) -> None:
        current = self._speaker_volume
        await self._set_speaker_volume((self._vol_min if current is None else current) + self._vol_step)

    async def async_volume_down(self) -> None:
        current = self._speaker_volume
        await self._set_speaker_volume((self._vol_min if current is None else current) - self._vol_step)

    async def async_mute_volume(self, mute: bool) -> None:
        await self._ensure_on()
        await self.coordinator.async_command(
            CMD_MUTE_SET, bytes([0x01 if mute else 0x00]), refresh=[Q_MUTE]
        )

    def _resolve_source(self, source: str) -> int:
        if source in self._source_map:
            return self._source_map[source]
        for code, name in SOURCES.items():
            if name.lower() == source.lower():
                return code
        try:
            return int(source, 16) if source.lower().startswith("0x") else int(source)
        except ValueError:
            raise ServiceValidationError(f"Source inconnue : {source}") from None

    async def _select(self, code: int, playlist: int | None) -> None:
        await self._ensure_on()
        try:
            await self.coordinator.client.async_set_input(code, playlist)
        except SICPError as exc:
            raise ServiceValidationError(
                f"Changement de source refusé ({source_name(code)}) : {exc}"
            ) from exc
        await self.coordinator.async_refresh_queries([Q_SOURCE])

    async def async_select_source(self, source: str) -> None:
        await self._select(self._resolve_source(source), None)

    async def async_select_source_playlist(self, source: str, playlist: int = 0) -> None:
        """Source Media Player / PDF Player / Browser avec playlist ou URL 1-7 (8 = USB autoplay)."""
        await self._select(self._resolve_source(source), playlist)

    async def _set_video_param(self, index: int, value: int) -> None:
        # 0xFF = « inchangé » (SICP ≥ 2.09) ; on repart de la dernière lecture
        # pour rester compatible avec les firmwares plus anciens.
        current = self.coordinator.payload(Q_VIDEO)
        frame = bytearray(current[:7]) if current and len(current) >= 7 else bytearray([0xFF] * 7)
        frame[index] = max(0, min(100, value))
        await self.coordinator.async_command(CMD_VIDEO_SET, bytes(frame), refresh=[Q_VIDEO])

    async def async_set_brightness(self, brightness: int) -> None:
        await self._set_video_param(0, brightness)

    async def async_set_contrast(self, contrast: int) -> None:
        await self._set_video_param(2, contrast)
