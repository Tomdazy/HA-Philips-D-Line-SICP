"""Philips D-Line media_player platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_EXPOSE_BRIGHTNESS,
    CONF_EXPOSE_CONTRAST,
    CONF_HOST,
    CONF_INPUTS,
    CONF_INPUT_CODE,
    CONF_INPUT_LABEL,
    CONF_MONITOR_ID,
    CONF_VOLUME_MAX,
    CONF_VOLUME_MIN,
    DEFAULT_EXPOSE_BRIGHTNESS,
    DEFAULT_EXPOSE_CONTRAST,
    DEFAULT_INPUTS,
    DEFAULT_VOLUME_MAX,
    DEFAULT_VOLUME_MIN,
    DOMAIN,
)
from .sicp import SICPError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Philips D-Line media player."""
    entry_data   = hass.data[DOMAIN][entry.entry_id]
    coordinator  = entry_data["coordinator"]
    client       = entry_data["client"]
    config       = entry_data["config"]

    async_add_entities(
        [PhilipsDLineMediaPlayer(coordinator, client, config, entry.entry_id)],
        update_before_add=True,
    )


class PhilipsDLineMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Philips D-Line display as a media player."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name directly

    def __init__(self, coordinator, client, config: dict, entry_id: str) -> None:
        super().__init__(coordinator)
        self._client     = client
        self._config     = config
        self._entry_id   = entry_id

        host       = config[CONF_HOST]
        monitor_id = config.get(CONF_MONITOR_ID, 1)

        self._attr_unique_id = f"philips_dline_{host}_{monitor_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=f"Philips D-Line ({host})",
            manufacturer="Philips",
            model="D-Line SICP",
        )

        # Build source list from config
        inputs = config.get(CONF_INPUTS, DEFAULT_INPUTS)
        self._source_map: dict[str, int] = {}
        for inp in inputs:
            label = inp[CONF_INPUT_LABEL]
            code  = inp[CONF_INPUT_CODE]
            if isinstance(code, str):
                code = int(code, 16) if code.startswith("0x") else int(code)
            self._source_map[label] = code
        self._source_map_inv: dict[int, str] = {v: k for k, v in self._source_map.items()}

        self._attr_source_list = list(self._source_map.keys())

        self._vol_min = config.get(CONF_VOLUME_MIN, DEFAULT_VOLUME_MIN)
        self._vol_max = config.get(CONF_VOLUME_MAX, DEFAULT_VOLUME_MAX)

        self._expose_brightness = config.get(CONF_EXPOSE_BRIGHTNESS, DEFAULT_EXPOSE_BRIGHTNESS)
        self._expose_contrast   = config.get(CONF_EXPOSE_CONTRAST, DEFAULT_EXPOSE_CONTRAST)

        # Supported features
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
        )

    # ──────────────────────────────────────────
    # State properties (from coordinator data)
    # ──────────────────────────────────────────

    @property
    def state(self) -> MediaPlayerState:
        data = self.coordinator.data or {}
        if data.get("power"):
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        data = self.coordinator.data or {}
        raw = data.get("volume")
        if raw is None:
            return None
        span = self._vol_max - self._vol_min
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (raw - self._vol_min) / span))

    @property
    def is_volume_muted(self) -> bool | None:
        data = self.coordinator.data or {}
        return data.get("muted")

    @property
    def source(self) -> str | None:
        data = self.coordinator.data or {}
        code = data.get("source")
        if code is None:
            return None
        return self._source_map_inv.get(code)

    # Extra state attributes for brightness / contrast
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        data = self.coordinator.data or {}
        if self._expose_brightness and data.get("brightness") is not None:
            attrs["brightness"] = data["brightness"]
        if self._expose_contrast and data.get("contrast") is not None:
            attrs["contrast"] = data["contrast"]
        return attrs

    # ──────────────────────────────────────────
    # Commands
    # ──────────────────────────────────────────

    async def async_turn_on(self) -> None:
        await self._call(self._client.async_set_power, True)

    async def async_turn_off(self) -> None:
        await self._call(self._client.async_set_power, False)

    async def async_mute_volume(self, mute: bool) -> None:
        await self._ensure_on()
        await self._call(self._client.async_set_mute, mute)

    async def async_set_volume_level(self, volume: float) -> None:
        await self._ensure_on()
        span = self._vol_max - self._vol_min
        level = round(self._vol_min + volume * span)
        await self._call(self._client.async_set_volume, level)

    async def async_volume_up(self) -> None:
        await self._ensure_on()
        data = self.coordinator.data or {}
        current = data.get("volume") or self._vol_min
        await self._call(self._client.async_set_volume, min(self._vol_max, current + 2))

    async def async_volume_down(self) -> None:
        await self._ensure_on()
        data = self.coordinator.data or {}
        current = data.get("volume") or self._vol_min
        await self._call(self._client.async_set_volume, max(self._vol_min, current - 2))

    async def async_select_source(self, source: str) -> None:
        await self._ensure_on()
        code = self._source_map.get(source)
        if code is None:
            _LOGGER.warning("Unknown source: %s", source)
            return
        await self._call(self._client.async_set_input, code)

    # Service calls exposed as HA services via entity platform
    async def async_set_brightness(self, brightness: int) -> None:
        """Set display brightness (0-100). Call via service."""
        await self._call(self._client.async_set_brightness, brightness)

    async def async_set_contrast(self, contrast: int) -> None:
        """Set display contrast (0-100). Call via service."""
        await self._call(self._client.async_set_contrast, contrast)

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    async def _ensure_on(self) -> None:
        """Power on the display if it is currently off."""
        data = self.coordinator.data or {}
        if not data.get("power"):
            _LOGGER.debug("Display is off, powering on before command")
            await self._call(self._client.async_set_power, True)

    async def _call(self, method, *args) -> None:
        """Call a SICP method, refresh coordinator, handle errors."""
        try:
            await method(*args)
        except SICPError as exc:
            _LOGGER.error("SICP command failed: %s", exc)
            return
        await self.coordinator.async_request_refresh()
