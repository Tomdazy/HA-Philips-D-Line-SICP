"""Plateforme number : réglages image, son et minuteries."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import NUMBERS, PhilipsNumberDescription
from .entity import PhilipsDescribedEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PhilipsNumber(runtime["coordinator"], runtime["config"], desc) for desc in NUMBERS
    )


class PhilipsNumber(PhilipsDescribedEntity, NumberEntity):
    entity_description: PhilipsNumberDescription

    @property
    def native_value(self) -> float | None:
        raw = self.byte(self.entity_description.index)
        if raw is None or raw == 0xFF:
            return None
        return raw * self.entity_description.scale

    async def async_set_native_value(self, value: float) -> None:
        raw = int(round(value / self.entity_description.scale))
        await self._write(self._frame(raw))
