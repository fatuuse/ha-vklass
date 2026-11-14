"""Shared base for per-child Vklass entities.

Children are keyed internally by student id. The device and entity names come from the child's name.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VklassCoordinator
from .summaries import entity_enabled_by_default

if TYPE_CHECKING:
    pass

_LOG = logging.getLogger(__name__)


class VklassChildEntity(CoordinatorEntity[VklassCoordinator]):
    """An entity belonging to one child's device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VklassCoordinator,
        entry: ConfigEntry,
        child_key: str,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._child_key = child_key
        child = coordinator.data["children"][child_key]

        self._attr_unique_id = f"{entry.entry_id}_{child_key}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{child_key}")},
            name=child["name"],
            manufacturer="Vklass",
        )
        self._attr_entity_registry_enabled_default = entity_enabled_by_default(child, key)

    @property
    def child(self) -> dict[str, Any]:
        return self.coordinator.data["children"].get(self._child_key, {})

    @property
    def available(self) -> bool:
        return super().available and self._child_key in self.coordinator.data["children"]


@callback
def async_track_child_removal(
    coordinator: VklassCoordinator,
    entry: ConfigEntry,
    entities_by_child: dict[str, list[VklassChildEntity]],
) -> None:
    """Schedule removal of per-child entities when a child disappears from coordinator data.

    Call once per platform after async_add_entities. Pass a dict mapping child key to the
    list of entities added for that child. Account-level entities are not tracked here.
    """
    async def _listener() -> None:
        current = set(coordinator.data.get("children", {}).keys())
        for key in list(entities_by_child.keys()):
            if key not in current:
                for entity in entities_by_child.pop(key):
                    _LOG.debug("Removing entity for disappeared child key %s", key)
                    await entity.async_remove()

    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: coordinator.hass.async_create_task(_listener())
        )
    )
