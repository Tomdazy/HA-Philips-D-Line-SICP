"""Config flow for Philips D-Line SICP integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_EXPOSE_BRIGHTNESS,
    CONF_EXPOSE_CONTRAST,
    CONF_GROUP_ID,
    CONF_HOST,
    CONF_INCLUDE_GROUP,
    CONF_INPUTS,
    CONF_MONITOR_ID,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_VOLUME_MAX,
    CONF_VOLUME_MIN,
    DEFAULT_EXPOSE_BRIGHTNESS,
    DEFAULT_EXPOSE_CONTRAST,
    DEFAULT_GROUP_ID,
    DEFAULT_INCLUDE_GROUP,
    DEFAULT_INPUTS,
    DEFAULT_MONITOR_ID,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_VOLUME_MAX,
    DEFAULT_VOLUME_MIN,
    DOMAIN,
)
from .sicp import PhilipsSICP, SICPError

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MONITOR_ID, default=DEFAULT_MONITOR_ID): vol.All(int, vol.Range(min=1, max=255)),
        vol.Optional(CONF_GROUP_ID,   default=DEFAULT_GROUP_ID):   vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional(CONF_INCLUDE_GROUP, default=DEFAULT_INCLUDE_GROUP): bool,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_POLL_INTERVAL,    default=DEFAULT_POLL_INTERVAL): vol.All(int, vol.Range(min=0, max=300)),
        vol.Optional(CONF_VOLUME_MIN,       default=DEFAULT_VOLUME_MIN):    vol.All(int, vol.Range(min=0, max=100)),
        vol.Optional(CONF_VOLUME_MAX,       default=DEFAULT_VOLUME_MAX):    vol.All(int, vol.Range(min=1, max=100)),
        vol.Optional(CONF_EXPOSE_BRIGHTNESS, default=DEFAULT_EXPOSE_BRIGHTNESS): bool,
        vol.Optional(CONF_EXPOSE_CONTRAST,   default=DEFAULT_EXPOSE_CONTRAST):   bool,
    }
)


class PhilipsDLineSICPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Philips D-Line SICP."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1 – connection parameters."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Test connection
            client = PhilipsSICP(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                monitor_id=user_input[CONF_MONITOR_ID],
                group_id=user_input[CONF_GROUP_ID],
                include_group=user_input[CONF_INCLUDE_GROUP],
            )
            try:
                ok = await client.async_ping()
                if not ok:
                    errors["base"] = "cannot_connect"
            except SICPError:
                errors["base"] = "cannot_connect"
            except (TimeoutError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"

            if not errors:
                # Avoid duplicate entries for the same host
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_MONITOR_ID]}"
                )
                self._abort_if_unique_id_configured()

                self._connection_data = user_input
                return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2 – display options."""
        if user_input is not None:
            data = {
                **self._connection_data,
                **user_input,
                CONF_INPUTS: DEFAULT_INPUTS,
            }
            return self.async_create_entry(
                title=f"Philips D-Line ({self._connection_data[CONF_HOST]})",
                data=data,
            )

        return self.async_show_form(
            step_id="options",
            data_schema=OPTIONS_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> PhilipsDLineOptionsFlow:
        """Return the options flow."""
        return PhilipsDLineOptionsFlow(config_entry)


class PhilipsDLineOptionsFlow(config_entries.OptionsFlow):
    """Handle options for an existing Philips D-Line entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options or self._config_entry.data

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=current.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(int, vol.Range(min=0, max=300)),
                vol.Optional(
                    CONF_VOLUME_MIN,
                    default=current.get(CONF_VOLUME_MIN, DEFAULT_VOLUME_MIN),
                ): vol.All(int, vol.Range(min=0, max=100)),
                vol.Optional(
                    CONF_VOLUME_MAX,
                    default=current.get(CONF_VOLUME_MAX, DEFAULT_VOLUME_MAX),
                ): vol.All(int, vol.Range(min=1, max=100)),
                vol.Optional(
                    CONF_EXPOSE_BRIGHTNESS,
                    default=current.get(CONF_EXPOSE_BRIGHTNESS, DEFAULT_EXPOSE_BRIGHTNESS),
                ): bool,
                vol.Optional(
                    CONF_EXPOSE_CONTRAST,
                    default=current.get(CONF_EXPOSE_CONTRAST, DEFAULT_EXPOSE_CONTRAST),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
