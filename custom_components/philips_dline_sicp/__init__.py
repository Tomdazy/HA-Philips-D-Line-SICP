"""Philips D-Line SICP integration for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOST,
    CONF_INCLUDE_GROUP,
    CONF_GROUP_ID,
    CONF_MONITOR_ID,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .sicp import PhilipsSICP, SICPConnectError, SICPError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Philips D-Line SICP from a config entry."""
    data = {**entry.data, **entry.options}

    client = PhilipsSICP(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, 5000),
        monitor_id=data.get(CONF_MONITOR_ID, 1),
        group_id=data.get(CONF_GROUP_ID, 0),
        include_group=data.get(CONF_INCLUDE_GROUP, True),
    )

    # Verify reachability at startup
    try:
        ok = await client.async_ping()
        if not ok:
            raise ConfigEntryNotReady(f"Display at {data[CONF_HOST]} did not respond")
    except SICPConnectError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    poll_interval = data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    coordinator = PhilipsDLineCoordinator(
        hass=hass,
        client=client,
        poll_interval=poll_interval,
    )

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "config": data,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register custom services
    _register_services(hass)

    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register integration-level services (idempotent)."""
    import voluptuous as vol
    from homeassistant.helpers import entity_platform

    async def _handle_set_brightness(call):
        entity_ids = call.data.get("entity_id", [])
        brightness = call.data["brightness"]
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            client = entry_data["client"]
            try:
                await client.async_set_brightness(brightness)
                entry_data["coordinator"].async_set_updated_data(
                    {**entry_data["coordinator"].data, "brightness": brightness}
                )
            except SICPError as exc:
                _LOGGER.error("set_brightness failed: %s", exc)

    async def _handle_set_contrast(call):
        contrast = call.data["contrast"]
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            client = entry_data["client"]
            try:
                await client.async_set_contrast(contrast)
                entry_data["coordinator"].async_set_updated_data(
                    {**entry_data["coordinator"].data, "contrast": contrast}
                )
            except SICPError as exc:
                _LOGGER.error("set_contrast failed: %s", exc)

    async def _handle_raw_command(call):
        cmd_str  = call.data["cmd"].strip()
        data_str = call.data.get("data", "").strip()
        try:
            cmd = int(cmd_str, 16) if cmd_str.startswith("0x") else int(cmd_str, 16)
            data = bytes.fromhex(data_str) if data_str else b""
        except ValueError as exc:
            _LOGGER.error("send_raw_command: invalid arguments: %s", exc)
            return
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            client = entry_data["client"]
            _LOGGER.warning(
                "send_raw_command → cmd=0x%02x data=%s", cmd, data.hex() or "(none)"
            )
            try:
                # Access private _send for raw diagnostics
                packet = client._build_packet(cmd, data)
                _LOGGER.warning("send_raw_command packet out: %s", packet.hex())
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(client.host, client.port),
                        timeout=5.0,
                    )
                    writer.write(packet)
                    await writer.drain()
                    try:
                        reply = await asyncio.wait_for(reader.read(64), timeout=2.0)
                        _LOGGER.warning(
                            "send_raw_command raw reply (%d bytes): %s", len(reply), reply.hex()
                        )
                    except Exception as exc:
                        _LOGGER.warning("send_raw_command: no reply: %s", exc)
                    finally:
                        writer.close()
                except Exception as exc:
                    _LOGGER.warning("send_raw_command: connect error: %s", exc)
            except Exception as exc:
                _LOGGER.error("send_raw_command failed: %s", exc)

    if not hass.services.has_service(DOMAIN, "set_brightness"):
        hass.services.async_register(
            DOMAIN, "set_brightness", _handle_set_brightness,
            schema=vol.Schema({vol.Required("brightness"): vol.All(int, vol.Range(min=0, max=100))})
        )
    if not hass.services.has_service(DOMAIN, "set_contrast"):
        hass.services.async_register(
            DOMAIN, "set_contrast", _handle_set_contrast,
            schema=vol.Schema({vol.Required("contrast"): vol.All(int, vol.Range(min=0, max=100))})
        )
    if not hass.services.has_service(DOMAIN, "send_raw_command"):
        hass.services.async_register(
            DOMAIN, "send_raw_command", _handle_raw_command,
            schema=vol.Schema({
                vol.Required("cmd"): str,
                vol.Optional("data", default=""): str,
            })
        )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update – reload the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


class PhilipsDLineCoordinator(DataUpdateCoordinator):
    """Coordinator that polls the display state periodically."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PhilipsSICP,
        poll_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval) if poll_interval > 0 else None,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch current display state."""
        try:
            power = await self.client.async_get_power()

            # Always attempt to fetch full state — some D-Line models respond
            # to volume/source queries even while in standby. Fall back to None
            # gracefully if the display refuses.
            volume = brightness = contrast = source = muted = None
            try:
                volume = await self.client.async_get_volume()
            except SICPError:
                pass
            try:
                muted = await self.client.async_get_mute()
            except SICPError:
                pass
            try:
                source = await self.client.async_get_input()
            except SICPError:
                pass
            try:
                brightness = await self.client.async_get_brightness()
            except SICPError:
                pass
            try:
                contrast = await self.client.async_get_contrast()
            except SICPError:
                pass

            return {
                "power":      power,
                "volume":     volume,
                "muted":      muted,
                "source":     source,
                "brightness": brightness,
                "contrast":   contrast,
            }
        except SICPError as exc:
            raise UpdateFailed(f"SICP error: {exc}") from exc
