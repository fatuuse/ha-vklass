"""Config flow and options flow for Vklass."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import VklassAuthError, VklassClient, VklassConnectionError
from .const import CALENDAR_CATEGORIES, DOMAIN, OPTION_CALENDAR_CATEGORIES, OPTION_SCHOOL_IDS

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

USER_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
})
REAUTH_SCHEMA = vol.Schema({
    vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
})


def _validate(username: str, password: str) -> None:
    VklassClient(username, password).login()


def child_fields(children: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """One form field per child, labelled with the child's name. Duplicate names get a number."""
    counts: dict[str, int] = {}
    fields: list[tuple[str, dict[str, Any]]] = []
    for child in children.values():
        name = child["name"]
        counts[name] = counts.get(name, 0) + 1
        field = name if counts[name] == 1 else f"{name} ({counts[name]})"
        fields.append((field, child))
    return fields


class VklassConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(_validate, username, password)
            except VklassAuthError:
                errors["base"] = "invalid_auth"
            except VklassConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=username,
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                await self.hass.async_add_executor_job(
                    _validate, entry.data[CONF_USERNAME], password
                )
            except VklassAuthError:
                errors["base"] = "invalid_auth"
            except VklassConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VklassOptionsFlow()


class VklassOptionsFlow(OptionsFlow):
    """School ids (found automatically, choose when several are found) and calendar categories."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        children: dict[str, dict[str, Any]] = self.config_entry.runtime_data.data["children"]
        fields = child_fields(children)

        if user_input is not None:
            school_ids: dict[str, int] = {}
            for field, child in fields:
                value = user_input.get(field)
                if value not in (None, "", 0):
                    school_ids[str(child["id"])] = int(value)
            return self.async_create_entry(
                title="",
                data={
                    OPTION_SCHOOL_IDS: school_ids,
                    OPTION_CALENDAR_CATEGORIES: user_input.get(
                        OPTION_CALENDAR_CATEGORIES, list(CALENDAR_CATEGORIES)
                    ),
                },
            )

        current_ids: dict[str, int] = self.config_entry.options.get(OPTION_SCHOOL_IDS, {})
        current_categories = self.config_entry.options.get(
            OPTION_CALENDAR_CATEGORIES, list(CALENDAR_CATEGORIES)
        )

        schema: dict[Any, Any] = {}
        for field, child in fields:
            candidates = [str(c) for c in child.get("school_candidates") or []]
            chosen = current_ids.get(str(child["id"])) or child.get("school_id")
            suggested = str(chosen) if len(candidates) > 1 and chosen else chosen
            if len(candidates) > 1:
                selector: Any = SelectSelector(
                    SelectSelectorConfig(options=candidates, mode=SelectSelectorMode.DROPDOWN)
                )
            else:
                selector = cv.positive_int
            schema[vol.Optional(field, description={"suggested_value": suggested})] = selector

        schema[vol.Optional(OPTION_CALENDAR_CATEGORIES, default=current_categories)] = SelectSelector(
            SelectSelectorConfig(
                options=list(CALENDAR_CATEGORIES),
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=OPTION_CALENDAR_CATEGORIES,
            )
        )
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
