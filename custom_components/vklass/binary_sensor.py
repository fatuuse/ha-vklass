"""Binary sensor platform for Vklass."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VklassConfigEntry
from .coordinator import VklassCoordinator
from .entity import VklassChildEntity, async_track_child_removal


@dataclass(frozen=True, kw_only=True)
class VklassChildBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


CHILD_BINARY_SENSORS: tuple[VklassChildBinarySensorDescription, ...] = (
    VklassChildBinarySensorDescription(
        key="gym_today",
        translation_key="gym_today",
        icon="mdi:run",
        value_fn=lambda c: bool(c.get("gym_today")),
    ),
    VklassChildBinarySensorDescription(
        key="gym_tomorrow",
        translation_key="gym_tomorrow",
        icon="mdi:run",
        value_fn=lambda c: bool(c.get("gym_tomorrow")),
    ),
    VklassChildBinarySensorDescription(
        key="holiday_confirmation",
        translation_key="holiday_confirmation",
        icon="mdi:calendar-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda c: bool(c.get("pending_holidays")),
        attrs_fn=lambda c: {"holidays": c.get("pending_holidays") or []},
    ),
    VklassChildBinarySensorDescription(
        key="absent_now",
        translation_key="absent_now",
        icon="mdi:account-off",
        device_class=BinarySensorDeviceClass.PRESENCE,
        value_fn=lambda c: c.get("absent_now"),
    ),
)


class VklassChildBinarySensor(VklassChildEntity, BinarySensorEntity):
    entity_description: VklassChildBinarySensorDescription

    def __init__(
        self,
        coordinator: VklassCoordinator,
        entry: VklassConfigEntry,
        child_name: str,
        description: VklassChildBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, child_name, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.child)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.child) if fn else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VklassConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities_by_child: dict[str, list] = {
        key: [VklassChildBinarySensor(coordinator, entry, key, d) for d in CHILD_BINARY_SENSORS]
        for key in coordinator.data["children"]
    }
    async_add_entities(e for child_entities in entities_by_child.values() for e in child_entities)
    async_track_child_removal(coordinator, entry, entities_by_child)
