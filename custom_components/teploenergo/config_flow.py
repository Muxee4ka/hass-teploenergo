from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import CONF_ACCOUNT_ID, CONF_LS, DOMAIN
from .exceptions import TeploenergoAuthError, TeploenergoConnectionError
from .teploenergo_api import TeploenergoApi

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class TeploenergoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api = TeploenergoApi(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                await api.authenticate()
                accounts = await api.get_accounts()
            except TeploenergoAuthError as exc:
                _LOGGER.error("Auth error: %s", exc)
                errors["base"] = "invalid_auth"
            except TeploenergoConnectionError as exc:
                _LOGGER.error("Connection error: %s", exc)
                errors["base"] = "cannot_connect"
            except Exception as exc:
                _LOGGER.exception("Unexpected error during config flow: %s", exc)
                errors["base"] = "unknown"
            else:
                if not accounts:
                    errors["base"] = "no_accounts"
                else:
                    # Schedule import flows for accounts 2..N
                    for account in accounts[1:]:
                        self.hass.async_create_task(
                            self.hass.config_entries.flow.async_init(
                                DOMAIN,
                                context={"source": "import"},
                                data={
                                    CONF_USERNAME: user_input[CONF_USERNAME],
                                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                                    CONF_LS: account.ls,
                                    CONF_ACCOUNT_ID: account.account_id,
                                },
                            )
                        )
                    first = accounts[0]
                    await self.async_set_unique_id(f"{DOMAIN}_{first.ls}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"ЛС {first.ls}",
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_LS: first.ls,
                            CONF_ACCOUNT_ID: first.account_id,
                        },
                    )
            finally:
                await api.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict) -> ConfigFlowResult:
        await self.async_set_unique_id(f"{DOMAIN}_{import_data[CONF_LS]}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"ЛС {import_data[CONF_LS]}",
            data=import_data,
        )

    async def async_step_reauth(self, entry_data: dict) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            api = TeploenergoApi(reauth_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                await api.authenticate()
            except TeploenergoAuthError:
                errors["base"] = "invalid_auth"
            except TeploenergoConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
            finally:
                await api.close()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"username": reauth_entry.data[CONF_USERNAME]},
            errors=errors,
        )
