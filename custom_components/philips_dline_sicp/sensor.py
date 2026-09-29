"""Plateforme sensor : température, compteur horaire et identification."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import SENSORS, PhilipsSensorDescription
from .entity import PhilipsDescribedEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PhilipsSensor(runtime["coordinator"], runtime["config"], desc) for desc in SENSORS
    )


class PhilipsSensor(PhilipsDescribedEntity, SensorEntity):
    entity_description: PhilipsSensorDescription

    @property
    def native_value(self):
        payload = self.payload
        if not payload:
            return None
        return self.entity_description.value_fn(payload)
