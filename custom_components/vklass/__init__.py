"""The Vklass integration."""
from __future__ import annotations

import logging
from datetime import date

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .api import VklassConnectionError
from .const import DOMAIN, KEEPALIVE_INTERVAL, PRESENCE_INTERVAL, RECOMPUTE_INTERVAL
from .coordinator import VklassCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.BUTTON]

type VklassConfigEntry = ConfigEntry[VklassCoordinator]

CONFIG_VERSION = 1


async def async_migrate_entry(hass: HomeAssistant, entry: VklassConfigEntry) -> bool:
    """Migrate old config entries. Only version 1 exists so far, so nothing needs converting."""
    _LOGGER.debug("Vklass config entry is at version %s", entry.version)
    return True


SERVICE_SET_CARE_DAY = "set_care_day"
SET_CARE_DAY_SCHEMA = vol.Schema(
    {
        vol.Required("student_id"): cv.positive_int,
        vol.Required("school_id"): cv.positive_int,
        vol.Required("date"): cv.date,
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
        vol.Optional("on_leave", default=False): cv.boolean,
        vol.Optional("message", default=""): cv.string,
    }
)


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_CARE_DAY):
        return

    async def _handle_set_care_day(call: ServiceCall) -> None:
        # Only administrators may change school data. Calls without a user (automations, scripts)
        # are system calls and are allowed.
        if call.context.user_id is not None:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise Unauthorized(context=call.context)
        student_id = call.data["student_id"]
        for loaded in hass.config_entries.async_entries(DOMAIN):
            if loaded.state is not ConfigEntryState.LOADED:
                continue
            coordinator = loaded.runtime_data
            children = (coordinator.data or {}).get("children", {})
            if any(child.get("id") == student_id for child in children.values()):
                break
        else:
            raise HomeAssistantError("No loaded Vklass account has a child with that student id")
        try:
            await hass.async_add_executor_job(
                coordinator.client.set_care_day,
                student_id,
                call.data["school_id"],
                call.data["date"],
                call.data["start"],
                call.data["end"],
                call.data["on_leave"],
                call.data["message"],
            )
        except VklassConnectionError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_SET_CARE_DAY, _handle_set_care_day, schema=SET_CARE_DAY_SCHEMA)


async def async_setup_entry(hass: HomeAssistant, entry: VklassConfigEntry) -> bool:
    coordinator = VklassCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Keepalive keeps the session (and a rotated cookie) alive between data updates
    entry.async_on_unload(async_track_time_interval(hass, coordinator.async_keepalive, KEEPALIVE_INTERVAL))
    # Attendance and care times during school start
    entry.async_on_unload(async_track_time_interval(hass, coordinator.async_presence_refresh, PRESENCE_INTERVAL))
    # Clock-dependent values, without network calls
    entry.async_on_unload(async_track_time_interval(hass, coordinator.async_recompute, RECOMPUTE_INTERVAL))
    entry.async_on_unload(coordinator.cancel_boundary)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: VklassConfigEntry) -> None:
    # Saving a rotated cookie also updates the entry. Only option changes should reload it.
    if dict(entry.options) == entry.runtime_data.applied_options:
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VklassConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
