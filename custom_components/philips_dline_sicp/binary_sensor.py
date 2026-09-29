"""Plateforme binary_sensor : présence d'un signal vidéo."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import BINARY_SENSORS, PhilipsBinarySensorDescription
from .entity import PhilipsDescribedEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PhilipsBinarySensor(runtime["coordinator"], runtime["config"], desc)
        for desc in BINARY_SENSORS
    )


class PhilipsBinarySensor(PhilipsDescribedEntity, BinarySensorEntity):
    entity_description: PhilipsBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        raw = self.byte(self.entity_description.index)
        return None if raw is None else raw == self.entity_description.on_value
