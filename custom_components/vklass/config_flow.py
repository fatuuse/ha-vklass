"""Config flow and options flow for Vklass.

Two ways to log in: username and password, or the Vklass session cookie. The cookie
works with BankID and other login methods, because the user logs in in a browser.

The same settings form is shown during setup and under Configure: school ids (found
automatically, choose when several are found), calendar categories and hiding
multi-day all-day events.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import VklassAuthError, VklassClient, VklassConnectionError
from .const import (
    AUTH_COOKIE,
    AUTH_PASSWORD,
    CALENDAR_CATEGORIES,
    CONF_AUTH_METHOD,
    DATA_COOKIE,
    DATA_PASSWORD,
    DATA_USERNAME,
    DOMAIN,
    OPTION_CALENDAR_CATEGORIES,
    OPTION_HIDE_MULTIDAY_ALLDAY,
    OPTION_SCHOOL_IDS,
)

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

METHOD_SCHEMA = vol.Schema({
    vol.Required(CONF_AUTH_METHOD, default=AUTH_PASSWORD): SelectSelector(
        SelectSelectorConfig(
            options=[AUTH_PASSWORD, AUTH_COOKIE],
            mode=SelectSelectorMode.LIST,
            translation_key="auth_method",
        )
    ),
})
PASSWORD_SCHEMA = vol.Schema({
    vol.Required(DATA_USERNAME): str,
    vol.Required(DATA_PASSWORD): PASSWORD_SELECTOR,
})
COOKIE_SCHEMA = vol.Schema({
    vol.Required(DATA_COOKIE): PASSWORD_SELECTOR,
})
REAUTH_PASSWORD_SCHEMA = vol.Schema({
    vol.Required(DATA_PASSWORD): PASSWORD_SELECTOR,
})


def _prepare_children(client: VklassClient) -> dict[str, dict[str, Any]]:
    """Children on the account, with school ids found, as the settings form needs them."""
    children = client.get_children()
    for child in children.values():
        if child["id"] is None:
            child["school_candidates"] = []
            continue
        found = set(client.discover_school_ids(child["id"]))
        if child["school_id"] is not None:
            found.add(child["school_id"])
        child["school_candidates"] = sorted(found)
        if child["school_id"] is None and found:
            child["school_id"] = min(found)
    return children


def _children_for_password(username: str, password: str) -> dict[str, dict[str, Any]]:
    client = VklassClient(username, password)
    client.login()
    return _prepare_children(client)


def _children_for_cookie(cookie: str) -> dict[str, dict[str, Any]]:
    """Raises if the cookie is not valid."""
    return _prepare_children(VklassClient(cookie=cookie))


def _validate_password(username: str, password: str) -> None:
    VklassClient(username, password).login()


def child_fields(children: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """One form field per child, labelled with the child's name. Duplicate names get a number."""
    counts: dict[str, int] = {}
    fields: list[tuple[str, dict[str, Any]]] = []
    for child in children.values():
        if child["id"] is None:
            continue
        name = child["name"]
        counts[name] = counts.get(name, 0) + 1
        field = name if counts[name] == 1 else f"{name} ({counts[name]})"
        fields.append((field, child))
    return fields


def _entry_title(data: dict[str, Any]) -> str:
    """Config entry title: "Vklass <username>". A cookie login has no username, so it is just "Vklass"."""
    username = data.get(DATA_USERNAME)
    return f"Vklass {username}" if username else "Vklass"


def settings_schema(children: dict[str, dict[str, Any]], current: dict[str, Any]) -> vol.Schema:
    """The settings form, used during setup and under Configure."""
    current_ids: dict[str, int] = current.get(OPTION_SCHOOL_IDS, {})
    current_categories = current.get(OPTION_CALENDAR_CATEGORIES, list(CALENDAR_CATEGORIES))
    current_hide = current.get(OPTION_HIDE_MULTIDAY_ALLDAY, False)

    schema: dict[Any, Any] = {}
    for field, child in child_fields(children):
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
    schema[vol.Optional(OPTION_HIDE_MULTIDAY_ALLDAY, default=current_hide)] = BooleanSelector()
    return vol.Schema(schema)


def settings_from_input(children: dict[str, dict[str, Any]], user_input: dict[str, Any]) -> dict[str, Any]:
    """Turn submitted settings into config entry options."""
    school_ids: dict[str, int] = {}
    for field, child in child_fields(children):
        value = user_input.get(field)
        if value not in (None, "", 0):
            school_ids[str(child["id"])] = int(value)
    return {
        OPTION_SCHOOL_IDS: school_ids,
        OPTION_CALENDAR_CATEGORIES: user_input.get(OPTION_CALENDAR_CATEGORIES, list(CALENDAR_CATEGORIES)),
        OPTION_HIDE_MULTIDAY_ALLDAY: bool(user_input.get(OPTION_HIDE_MULTIDAY_ALLDAY, False)),
    }


class VklassConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._children: dict[str, dict[str, Any]] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_AUTH_METHOD] == AUTH_COOKIE:
                return await self.async_step_cookie()
            return await self.async_step_password()
        return self.async_show_form(step_id="user", data_schema=METHOD_SCHEMA)

    async def async_step_password(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[DATA_USERNAME].strip()
            password = user_input[DATA_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            try:
                children = await self.hass.async_add_executor_job(_children_for_password, username, password)
            except VklassAuthError:
                errors["base"] = "invalid_auth"
            except VklassConnectionError:
                errors["base"] = "cannot_connect"
            else:
                self._data = {CONF_AUTH_METHOD: AUTH_PASSWORD, DATA_USERNAME: username, DATA_PASSWORD: password}
                self._children = children
                return await self.async_step_settings()

        return self.async_show_form(step_id="password", data_schema=PASSWORD_SCHEMA, errors=errors)

    async def async_step_cookie(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            cookie = user_input[DATA_COOKIE].strip()
            try:
                children = await self.hass.async_add_executor_job(_children_for_cookie, cookie)
            except VklassAuthError:
                errors["base"] = "invalid_cookie"
            except VklassConnectionError:
                errors["base"] = "cannot_connect"
            else:
                # The student ids identify the account, so the same account cannot be added twice.
                ids = sorted(str(c["id"]) for c in children.values() if c["id"] is not None)
                if not ids:
                    errors["base"] = "no_children"
                else:
                    await self.async_set_unique_id("cookie-" + "-".join(ids))
                    self._abort_if_unique_id_configured()
                    self._data = {CONF_AUTH_METHOD: AUTH_COOKIE, DATA_COOKIE: cookie}
                    self._children = children
                    return await self.async_step_settings()

        return self.async_show_form(step_id="cookie", data_schema=COOKIE_SCHEMA, errors=errors)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=_entry_title(self._data),
                data=self._data,
                options=settings_from_input(self._children, user_input),
            )
        return self.async_show_form(
            step_id="settings",
            data_schema=settings_schema(self._children, {}),
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        is_cookie = entry.data.get(CONF_AUTH_METHOD) == AUTH_COOKIE

        if user_input is not None:
            try:
                if is_cookie:
                    cookie = user_input[DATA_COOKIE].strip()
                    await self.hass.async_add_executor_job(_children_for_cookie, cookie)
                    updates: dict[str, Any] = {DATA_COOKIE: cookie}
                else:
                    password = user_input[DATA_PASSWORD]
                    await self.hass.async_add_executor_job(
                        _validate_password, entry.data[DATA_USERNAME], password
                    )
                    updates = {DATA_PASSWORD: password}
            except VklassAuthError:
                errors["base"] = "invalid_cookie" if is_cookie else "invalid_auth"
            except VklassConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=updates)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=COOKIE_SCHEMA if is_cookie else REAUTH_PASSWORD_SCHEMA,
            errors=errors,
            description_placeholders={"username": entry.data.get(DATA_USERNAME, "")},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VklassOptionsFlow()


class VklassOptionsFlow(OptionsFlow):
    """The same settings as during setup, changed later under Configure."""

    def _children(self) -> dict[str, dict[str, Any]]:
        """Children of the loaded integration. Empty if setup failed, so the flow still opens."""
        runtime = getattr(self.config_entry, "runtime_data", None)
        if runtime is None or not runtime.data:
            return {}
        return runtime.data.get("children", {})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        children = self._children()
        if user_input is not None:
            options = settings_from_input(children, user_input)
            if not children:
                # No school fields were shown, so keep the school ids that are already stored.
                options[OPTION_SCHOOL_IDS] = dict(self.config_entry.options.get(OPTION_SCHOOL_IDS, {}))
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="init",
            data_schema=settings_schema(children, dict(self.config_entry.options)),
        )
