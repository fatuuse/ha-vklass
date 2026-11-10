"""Shared base for per-child Vklass entities.

Children are keyed internally by student id. The device and entity names come from the child's name.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VklassCoordinator
from .summaries import entity_enabled_by_default


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
        self._attr_entity_registry_enabled_default = entity_enabled_by_default(child, key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{child_key}")},
            name=child["name"],
            manufacturer="Vklass",
        )

    @property
    def child(self) -> dict[str, Any]:
        return self.coordinator.data["children"].get(self._child_key, {})

    @property
    def available(self) -> bool:
        return super().available and self._child_key in self.coordinator.data["children"]
