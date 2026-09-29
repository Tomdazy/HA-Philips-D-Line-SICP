"""Plateforme switch : fonctions activables."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import SWITCHES, PhilipsSwitchDescription
from .entity import PhilipsDescribedEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PhilipsSwitch(runtime["coordinator"], runtime["config"], desc) for desc in SWITCHES
    )


class PhilipsSwitch(PhilipsDescribedEntity, SwitchEntity):
    entity_description: PhilipsSwitchDescription

    @property
    def is_on(self) -> bool | None:
        raw = self.byte(self.entity_description.index)
        if raw is None or raw == 0xFF:  # 0xFF : matériel absent (capteur de lumière…)
            return None
        return raw == self.entity_description.on_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(self._frame(self.entity_description.on_value))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(self._frame(self.entity_description.off_value))
