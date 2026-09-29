"""Plateforme light : rétroéclairage (marche/arrêt 0x72 + luminosité 0x32).

Exposé via HomeKit Bridge, il apparaît comme une ampoule variable : c'est
le moyen de régler la luminosité de l'écran depuis l'app Maison.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TIER_FAST, PhilipsDLineCoordinator
from .descriptions import frame_with
from .entity import PhilipsDLineEntity, device_unique_id
from .sicp import CMD_VIDEO_GET, CMD_VIDEO_SET

CMD_BACKLIGHT_GET = 0x71
CMD_BACKLIGHT_SET = 0x72
Q_BACKLIGHT = (CMD_BACKLIGHT_GET, b"")
Q_VIDEO = (CMD_VIDEO_GET, b"")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PhilipsBacklight(runtime["coordinator"], runtime["config"])])


class PhilipsBacklight(PhilipsDLineEntity, LightEntity):
    _attr_translation_key = "backlight"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator: PhilipsDLineCoordinator, config: dict) -> None:
        super().__init__(coordinator, config)
        self._attr_unique_id = f"{device_unique_id(config)}_backlight"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.register(Q_BACKLIGHT, TIER_FAST))
        self.async_on_remove(self.coordinator.register(Q_VIDEO, TIER_FAST))

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.power is None:
            return None
        if not self.coordinator.power:
            return False
        backlight = self.coordinator.payload(Q_BACKLIGHT)
        # 0x71 : 0x00 = rétroéclairage allumé, 0x01 = éteint
        return True if not backlight else backlight[0] == 0x00

    @property
    def brightness(self) -> int | None:
        video = self.coordinator.payload(Q_VIDEO)
        if not video or video[0] > 100:
            return None
        return round(video[0] * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.coordinator.power is False:
            await self.coordinator.async_set_power(True)
        backlight = self.coordinator.payload(Q_BACKLIGHT)
        if backlight and backlight[0] != 0x00:
            await self.coordinator.async_command(
                CMD_BACKLIGHT_SET, b"\x00", refresh=[Q_BACKLIGHT]
            )
        if ATTR_BRIGHTNESS in kwargs:
            level = max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))
            data = frame_with(self.coordinator.payload(Q_VIDEO), 7, 0xFF, 0, level)
            await self.coordinator.async_command(CMD_VIDEO_SET, data, refresh=[Q_VIDEO])

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Coupe seulement le rétroéclairage : le son et l'électronique restent actifs
        await self.coordinator.async_command(CMD_BACKLIGHT_SET, b"\x01", refresh=[Q_BACKLIGHT])
