"""Entité de base Philips D-Line."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, CONF_MONITOR_ID, DOMAIN
from .coordinator import (
    Q_ANDROID_FW,
    Q_FIRMWARE,
    Q_MODEL,
    Q_PLATFORM,
    Q_PLATFORM_VER,
    Q_SERIAL,
    TIER_SLOW,
    PhilipsDLineCoordinator,
    Query,
)
from .descriptions import frame_with


def decode_text(payload: bytes | None) -> str | None:
    if not payload:
        return None
    text = payload.decode("ascii", errors="ignore").strip("\x00 ").strip()
    return text or None


def device_unique_id(config: dict) -> str:
    return f"philips_dline_{config[CONF_HOST]}_{config.get(CONF_MONITOR_ID, 1)}"


def build_device_info(coordinator: PhilipsDLineCoordinator, config: dict) -> DeviceInfo:
    model = decode_text(coordinator.payload(Q_MODEL))
    platform = decode_text(coordinator.payload(Q_PLATFORM_VER)) or decode_text(
        coordinator.payload(Q_PLATFORM)
    )
    firmware = decode_text(coordinator.payload(Q_ANDROID_FW)) or decode_text(
        coordinator.payload(Q_FIRMWARE)
    )
    return DeviceInfo(
        identifiers={(DOMAIN, device_unique_id(config))},
        name=f"Philips {model}" if model else f"Philips D-Line ({config[CONF_HOST]})",
        manufacturer="Philips",
        model=model or "Professional Display (SICP)",
        hw_version=platform,
        sw_version=firmware,
        serial_number=decode_text(coordinator.payload(Q_SERIAL)),
        configuration_url=None,
    )


class PhilipsDLineEntity(CoordinatorEntity[PhilipsDLineCoordinator]):
    """Entité adossée à une ou plusieurs requêtes Get du coordinateur."""

    _attr_has_entity_name = True
    # Requête principale : l'entité est indisponible tant qu'elle n'a pas de réponse
    query: Query | None = None
    tier: str = TIER_SLOW
    # Disponible même en veille (valeur figée sur la dernière lecture)
    available_when_off: bool = True

    def __init__(
        self,
        coordinator: PhilipsDLineCoordinator,
        config: dict,
        description: EntityDescription | None = None,
    ) -> None:
        super().__init__(coordinator)
        if description is not None:
            self.entity_description = description
            self._attr_unique_id = f"{device_unique_id(config)}_{description.key}"
        self._config = config
        self._attr_device_info = build_device_info(coordinator, config)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.query is not None:
            self.async_on_remove(self.coordinator.register(self.query, self.tier))

    @property
    def payload(self) -> bytes | None:
        if self.query is None:
            return None
        return self.coordinator.payload(self.query)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if not self.available_when_off and self.coordinator.power is False:
            return False
        if self.query is not None:
            return self.payload is not None
        return True

    def byte(self, index: int) -> int | None:
        payload = self.payload
        if payload is None or len(payload) <= index:
            return None
        return payload[index]


class PhilipsDescribedEntity(PhilipsDLineEntity):
    """Entité pilotée par une description SICPMixin (voir descriptions.py)."""

    def __init__(self, coordinator: PhilipsDLineCoordinator, config: dict, description) -> None:
        super().__init__(coordinator, config, description)
        self.query = description.query
        self.tier = description.tier
        self.available_when_off = description.available_when_off

    async def _write(self, data: bytes) -> None:
        await self.coordinator.async_command(
            self.entity_description.set_cmd, data, refresh=[self.query]
        )

    def _frame(self, value: int) -> bytes:
        desc = self.entity_description
        return frame_with(self.payload, desc.frame_len, desc.fill, desc.index, value)
