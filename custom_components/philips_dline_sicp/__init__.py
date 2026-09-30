"""Intégration Philips D-Line (SICP) pour Home Assistant."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_GROUP_ID,
    CONF_HOST,
    CONF_INCLUDE_GROUP,
    CONF_MAC,
    CONF_MONITOR_ID,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_SLOW_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SLOW_POLL_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import PhilipsDLineCoordinator
from .sicp import PhilipsSICP, SICPError
from .wol import lookup_mac, normalize_mac

CONF_CACHE = "cache"

_LOGGER = logging.getLogger(__name__)

SERVICE_RAW_COMMAND = "send_raw_command"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Enregistre les services de niveau intégration."""

    async def _handle_raw_command(call: ServiceCall) -> ServiceResponse:
        try:
            cmd = int(call.data["cmd"].strip(), 16)
            data = bytes.fromhex(call.data.get("data", "").replace(" ", ""))
        except ValueError as exc:
            raise ServiceValidationError(f"Arguments invalides : {exc}") from exc

        host = call.data.get("host")
        results = []
        for runtime in hass.data.get(DOMAIN, {}).values():
            client: PhilipsSICP = runtime["client"]
            if host and client.host != host:
                continue
            result = {"host": client.host, "request": client.build_packet(cmd, data).hex(" ")}
            try:
                echo, payload = await client.send(cmd, data)
                result.update(echo=f"0x{echo:02X}", payload=payload.hex(" "))
            except SICPError as exc:
                result["error"] = str(exc)
            _LOGGER.info("send_raw_command : %s", result)
            results.append(result)
        if not results:
            raise ServiceValidationError("Aucun moniteur Philips D-Line ne correspond")
        return {"results": results}

    hass.services.async_register(
        DOMAIN,
        SERVICE_RAW_COMMAND,
        _handle_raw_command,
        schema=vol.Schema({
            vol.Required("cmd"): cv.string,
            vol.Optional("data", default=""): cv.string,
            vol.Optional("host"): cv.string,
        }),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = {**entry.data, **entry.options}

    client = PhilipsSICP(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, 5000),
        monitor_id=data.get(CONF_MONITOR_ID, 1),
        group_id=data.get(CONF_GROUP_ID, 0),
        include_group=data.get(CONF_INCLUDE_GROUP, True),
    )

    coordinator = PhilipsDLineCoordinator(
        hass=hass,
        client=client,
        poll_interval=data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        slow_poll_interval=data.get(CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_INTERVAL),
        # Option saisie par l'utilisateur, sinon adresse détectée automatiquement
        mac=normalize_mac(entry.options.get(CONF_MAC)) or normalize_mac(entry.data.get(CONF_MAC)),
        cache=entry.data.get(CONF_CACHE),
    )
    # Un moniteur en veille ne répond souvent plus en SICP : on démarre quand
    # même (identité reprise du cache) pour que la télévision reste présente
    # dans HomeKit et puisse être rallumée, par Wake on LAN si besoin.
    await coordinator.async_fetch_identity()
    await coordinator.async_refresh()

    # Adresse MAC détectée dans la table ARP après l'échange avec le moniteur
    if coordinator.mac is None:
        coordinator.mac = await hass.async_add_executor_job(lookup_mac, client.host)
    _async_save_cache(hass, entry, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "config": data,
        "options": dict(entry.options),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_complete_identity() -> None:
        if coordinator.mac is None and coordinator.reachable:
            coordinator.mac = await hass.async_add_executor_job(lookup_mac, client.host)
        _async_save_cache(hass, entry, coordinator)

    # Identité ou MAC encore inconnues au démarrage : on les mémorise dès que
    # le moniteur répond (typiquement au premier allumage)
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: hass.async_create_task(_async_complete_identity())
        )
    )

    # Les entités viennent de déclarer leurs requêtes : première lecture complète
    await coordinator.async_request_refresh()
    return True


def _async_save_cache(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: PhilipsDLineCoordinator
) -> None:
    """Mémorise identité, sources et MAC pour les prochains démarrages."""
    new_data = {**entry.data, CONF_CACHE: coordinator.cache_snapshot()}
    if coordinator.mac and not normalize_mac(entry.data.get(CONF_MAC)):
        new_data[CONF_MAC] = coordinator.mac
    if new_data != dict(entry.data):
        hass.config_entries.async_update_entry(entry, data=new_data)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    # Seul un changement d'options justifie un rechargement (pas la mise à jour du cache)
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is not None and runtime["options"] == dict(entry.options):
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime = hass.data[DOMAIN].pop(entry.entry_id, {})
        client = runtime.get("client")
        if client is not None:
            await client.disconnect()
    return unload_ok
