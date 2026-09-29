"""Plateforme select : modes et réglages à choix multiples."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import SELECTS, PhilipsSelectDescription
from .entity import PhilipsDescribedEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PhilipsSelect(runtime["coordinator"], runtime["config"], desc) for desc in SELECTS
    )


class PhilipsSelect(PhilipsDescribedEntity, SelectEntity):
    entity_description: PhilipsSelectDescription

    def __init__(self, coordinator, config, description: PhilipsSelectDescription) -> None:
        super().__init__(coordinator, config, description)
        self._codes = {option: code for code, option in description.values.items()}

    @property
    def current_option(self) -> str | None:
        raw = self.byte(self.entity_description.index)
        if raw is None:
            return None
        return self.entity_description.values.get(raw & self.entity_description.mask)

    async def async_select_option(self, option: str) -> None:
        desc = self.entity_description
        if desc.frames is not None and option in desc.frames:
            await self._write(desc.frames[option])
            return
        if option not in self._codes:
            raise ServiceValidationError(f"Option inconnue : {option}")
        await self._write(self._frame(self._codes[option]))
