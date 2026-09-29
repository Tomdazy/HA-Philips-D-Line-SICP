"""Plateforme button : actions ponctuelles (redémarrage, capture…)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import BUTTONS, PhilipsButtonDescription
from .entity import PhilipsDLineEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PhilipsButton(runtime["coordinator"], runtime["config"], desc) for desc in BUTTONS
    )


class PhilipsButton(PhilipsDLineEntity, ButtonEntity):
    entity_description: PhilipsButtonDescription

    async def async_press(self) -> None:
        desc = self.entity_description
        await self.coordinator.async_command(desc.cmd, desc.data)
