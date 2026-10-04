"""Config flow for Buy Me a Pie."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    BuyMeAPieAuthError,
    BuyMeAPieClient,
    BuyMeAPieConnectionError,
    BuyMeAPieError,
)
from .const import CONF_PIN, DOMAIN

PIN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class BuyMeAPieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Buy Me a Pie."""

    VERSION = 1

    async def _validate(self, username: str, pin: str) -> str | None:
        """Return an error key or None if the credentials work."""
        client = BuyMeAPieClient(async_create_clientsession(self.hass), username, pin)
        try:
            await client.async_login()
        except BuyMeAPieAuthError:
            return "invalid_auth"
        except BuyMeAPieConnectionError:
            return "cannot_connect"
        except BuyMeAPieError:
            return "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            if error := await self._validate(username, user_input[CONF_PIN]):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=username,
                    data={CONF_USERNAME: username, CONF_PIN: user_input[CONF_PIN]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PIN): PIN_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if error := await self._validate(
                entry.data[CONF_USERNAME], user_input[CONF_PIN]
            ):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PIN: user_input[CONF_PIN]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PIN): PIN_SELECTOR}),
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )
