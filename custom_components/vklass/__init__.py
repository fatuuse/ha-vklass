"""The Vklass integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import KEEPALIVE_INTERVAL
from .coordinator import VklassCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.BUTTON]

type VklassConfigEntry = ConfigEntry[VklassCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: VklassConfigEntry) -> bool:
    coordinator = VklassCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Keepalive keeps the session (and a rotated cookie) alive between data updates
    entry.async_on_unload(
        async_track_time_interval(hass, coordinator.async_keepalive, KEEPALIVE_INTERVAL)
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: VklassConfigEntry) -> None:
    # Saving a rotated cookie also updates the entry. Only option changes should reload it.
    if dict(entry.options) == entry.runtime_data.applied_options:
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VklassConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
