"""Plateforme time : horloge interne et heure du redémarrage automatique."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import TIMES, PhilipsTimeDescription, frame_with
from .entity import PhilipsDescribedEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PhilipsTime(runtime["coordinator"], runtime["config"], desc) for desc in TIMES
    )


class PhilipsTime(PhilipsDescribedEntity, TimeEntity):
    entity_description: PhilipsTimeDescription

    @property
    def native_value(self) -> time | None:
        idx = self.entity_description.hour_index
        hour, minute = self.byte(idx), self.byte(idx + 1)
        # 24 h / 60 min = valeur NULL côté moniteur
        if hour is None or minute is None or hour > 23 or minute > 59:
            return None
        return time(hour, minute)

    async def async_set_value(self, value: time) -> None:
        desc = self.entity_description
        frame = bytearray(
            frame_with(self.payload, desc.frame_len, desc.fill, desc.hour_index, value.hour)
        )
        frame[desc.hour_index + 1] = value.minute
        await self._write(bytes(frame))
