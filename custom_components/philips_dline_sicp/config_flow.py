"""Config flow de l'intégration Philips D-Line SICP."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_GROUP_ID,
    CONF_HOST,
    CONF_INCLUDE_GROUP,
    CONF_MAC,
    CONF_MONITOR_ID,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_SLOW_POLL_INTERVAL,
    CONF_SOURCES,
    CONF_VOLUME_MAX,
    CONF_VOLUME_MIN,
    CONF_VOLUME_STEP,
    DEFAULT_GROUP_ID,
    DEFAULT_INCLUDE_GROUP,
    DEFAULT_MONITOR_ID,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLOW_POLL_INTERVAL,
    DEFAULT_SOURCES,
    DEFAULT_VOLUME_MAX,
    DEFAULT_VOLUME_MIN,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    SOURCES,
    source_name,
)
from .sicp import PhilipsSICP, SICPError
from .wol import normalize_mac

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MONITOR_ID, default=DEFAULT_MONITOR_ID): vol.All(int, vol.Range(min=1, max=255)),
        vol.Optional(CONF_GROUP_ID, default=DEFAULT_GROUP_ID): vol.All(int, vol.Range(min=0, max=254)),
        vol.Optional(CONF_INCLUDE_GROUP, default=DEFAULT_INCLUDE_GROUP): bool,
    }
)


def _options_schema(current: dict[str, Any], available: list[int]) -> vol.Schema:
    """Schéma des options ; `available` = sources proposées à la sélection."""
    # Moniteur incapable de lister ses sources (0xAB) : catalogue complet,
    # avec une présélection raisonnable
    choices = list(dict.fromkeys(available)) or list(SOURCES)
    selected = [int(c) for c in current.get(CONF_SOURCES) or available or DEFAULT_SOURCES]
    # Une source choisie auparavant reste proposée même si le moniteur ne l'annonce plus
    choices += [c for c in selected if c not in choices]
    options = [SelectOptionDict(value=str(c), label=source_name(c)) for c in choices]

    return vol.Schema(
        {
            vol.Optional(
                CONF_SOURCES, default=[str(c) for c in selected if c in choices]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=options, multiple=True, mode=SelectSelectorMode.LIST
                )
            ),
            vol.Optional(
                CONF_POLL_INTERVAL,
                default=current.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            ): vol.All(int, vol.Range(min=0, max=300)),
            vol.Optional(
                CONF_SLOW_POLL_INTERVAL,
                default=current.get(CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_INTERVAL),
            ): vol.All(int, vol.Range(min=30, max=3600)),
            vol.Optional(
                CONF_VOLUME_MIN, default=current.get(CONF_VOLUME_MIN, DEFAULT_VOLUME_MIN)
            ): vol.All(int, vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_VOLUME_MAX, default=current.get(CONF_VOLUME_MAX, DEFAULT_VOLUME_MAX)
            ): vol.All(int, vol.Range(min=1, max=100)),
            vol.Optional(
                CONF_VOLUME_STEP, default=current.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
            ): vol.All(int, vol.Range(min=1, max=20)),
            # Vide = adresse détectée automatiquement
            vol.Optional(
                CONF_MAC, description={"suggested_value": current.get(CONF_MAC, "")}
            ): str,
        }
    )


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    result = dict(user_input)
    result[CONF_SOURCES] = [int(c) for c in user_input.get(CONF_SOURCES, [])]
    if CONF_MAC in result:
        result[CONF_MAC] = normalize_mac(result[CONF_MAC]) or ""
    return result


class PhilipsDLineSICPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Ajout d'un moniteur Philips D-Line."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_data: dict[str, Any] = {}
        self._available_sources: list[int] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = PhilipsSICP(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                monitor_id=user_input[CONF_MONITOR_ID],
                group_id=user_input[CONF_GROUP_ID],
                include_group=user_input[CONF_INCLUDE_GROUP],
            )
            try:
                if not await client.async_ping():
                    errors["base"] = "cannot_connect"
                else:
                    try:
                        self._available_sources = await client.async_get_sources()
                    except SICPError:
                        self._available_sources = []
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Erreur inattendue pendant la configuration")
                errors["base"] = "unknown"
            finally:
                await client.disconnect()

            if not errors:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_MONITOR_ID]}"
                )
                self._abort_if_unique_id_configured()
                self._connection_data = user_input
                return await self.async_step_options()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=f"Philips D-Line ({self._connection_data[CONF_HOST]})",
                data={**self._connection_data, **_normalize(user_input)},
            )
        return self.async_show_form(
            step_id="options",
            data_schema=_options_schema({}, self._available_sources),
            description_placeholders={"count": str(len(self._available_sources))},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> PhilipsDLineOptionsFlow:
        return PhilipsDLineOptionsFlow(config_entry)


class PhilipsDLineOptionsFlow(config_entries.OptionsFlow):
    """Modification des options d'un moniteur existant."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=_normalize(user_input))

        current = {**self._entry.data, **self._entry.options}
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        available = list(runtime["coordinator"].sources) if runtime else []
        return self.async_show_form(step_id="init", data_schema=_options_schema(current, available))
