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
from .entity import VklassChildEntity


@dataclass(frozen=True, kw_only=True)
class VklassChildBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


CHILD_BINARY_SENSORS: tuple[VklassChildBinarySensorDescription, ...] = (
    VklassChildBinarySensorDescription(
        key="gym_today",
        name="Gym today",
        icon="mdi:run",
        value_fn=lambda c: bool(c.get("gym_today")),
    ),
    VklassChildBinarySensorDescription(
        key="gym_tomorrow",
        name="Gym tomorrow",
        icon="mdi:run",
        value_fn=lambda c: bool(c.get("gym_tomorrow")),
    ),
    VklassChildBinarySensorDescription(
        key="holiday_confirmation",
        name="Holiday confirmation needed",
        icon="mdi:calendar-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda c: bool(c.get("pending_holidays")),
        attrs_fn=lambda c: {"holidays": c.get("pending_holidays") or []},
    ),    VklassChildBinarySensorDescription(
        key="absent_now",
        name="Absent now",
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
    async_add_entities(
        VklassChildBinarySensor(coordinator, entry, child_name, description)
        for child_name in coordinator.data["children"]
        for description in CHILD_BINARY_SENSORS
    )
