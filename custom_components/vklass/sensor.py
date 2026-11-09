"""Sensor platform for Vklass."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VklassConfigEntry
from .const import DOMAIN, NEWS_DAYS
from .coordinator import VklassCoordinator
from .entity import VklassChildEntity


@dataclass(frozen=True, kw_only=True)
class VklassChildSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


CHILD_SENSORS: tuple[VklassChildSensorDescription, ...] = (
    VklassChildSensorDescription(
        key="care_time",
        name="Care time",
        icon="mdi:clock-outline",
        value_fn=lambda c: c.get("caretime"),
    ),
    VklassChildSensorDescription(
        key="attendance",
        name="Attendance",
        icon="mdi:account-check",
        value_fn=lambda c: c.get("check"),
    ),
    VklassChildSensorDescription(
        key="next_lesson",
        name="Next lesson",
        icon="mdi:calendar-clock",
        value_fn=lambda c: (c.get("next_event") or {}).get("title"),
        attrs_fn=lambda c: dict(c.get("next_event") or {}),
    ),
    VklassChildSensorDescription(
        key="care_today",
        name="Care today",
        icon="mdi:calendar-account",
        value_fn=lambda c: (c.get("care_today") or {}).get("state"),
        attrs_fn=lambda c: {
            **{k: v for k, v in (c.get("care_today") or {}).items() if k != "state"},
            "schedule": c.get("care_schedule") or [],
        },
    ),
    VklassChildSensorDescription(
        key="care_tomorrow",
        name="Care tomorrow",
        icon="mdi:calendar-arrow-right",
        value_fn=lambda c: (c.get("care_tomorrow") or {}).get("state"),
        attrs_fn=lambda c: {k: v for k, v in (c.get("care_tomorrow") or {}).items() if k != "state"},
    ),
    VklassChildSensorDescription(
        key="absences_upcoming",
        name="Upcoming absences",
        icon="mdi:calendar-remove",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get("absences_upcoming"),
        attrs_fn=lambda c: {"absences": c.get("absences") or []},
    ),
    VklassChildSensorDescription(
        key="menu_days",
        name="Menu days",
        icon="mdi:silverware-fork-knife",
        value_fn=lambda c: len(c.get("food") or {}),
        attrs_fn=lambda c: {"menu": c.get("food") or {}},
    ),
)


GRADE_SENSORS: tuple[VklassChildSensorDescription, ...] = (
    VklassChildSensorDescription(
        key="merit_value",
        name="Merit value",
        icon="mdi:school",
        value_fn=lambda c: c.get("merit_value"),
        attrs_fn=lambda c: {"term": c.get("merit_term"), "history": c.get("merit_history") or {}},
    ),
    VklassChildSensorDescription(
        key="current_grades",
        name="Current grades",
        icon="mdi:format-list-numbered",
        value_fn=lambda c: None if c.get("grade_term") is None else len(c.get("grades_current") or {}),
        attrs_fn=lambda c: {
            "term": c.get("grade_term"),
            "grades": c.get("grades_current") or {},
            "history": c.get("grades_history") or {},
        },
    ),
)


COURSE_SENSORS: tuple[VklassChildSensorDescription, ...] = (
    VklassChildSensorDescription(
        key="courses_active",
        name="Active courses",
        icon="mdi:book-open-variant",
        value_fn=lambda c: c.get("courses_active"),
        attrs_fn=lambda c: {"courses": c.get("courses") or []},
    ),
    VklassChildSensorDescription(
        key="course_attendance",
        name="Course attendance",
        icon="mdi:account-clock",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get("courses_attendance"),
    ),
)


class VklassChildSensor(VklassChildEntity, SensorEntity):
    entity_description: VklassChildSensorDescription

    def __init__(
        self,
        coordinator: VklassCoordinator,
        entry: ConfigEntry,
        child_name: str,
        description: VklassChildSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, child_name, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.child)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.child) if fn else None


class VklassNewsSensor(CoordinatorEntity[VklassCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = f"News (last {NEWS_DAYS} days)"
    _attr_icon = "mdi:newspaper-variant-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VklassCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_news"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Vklass",
            manufacturer="Vklass",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("news") or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"articles": self.coordinator.data.get("news") or []}


@dataclass(frozen=True, kw_only=True)
class VklassServiceSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


SERVICE_SENSORS: tuple[VklassServiceSensorDescription, ...] = (
    VklassServiceSensorDescription(
        key="messages",
        name="Unread messages",
        icon="mdi:message-badge-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (d.get("scoreboard") or {}).get("messages"),
    ),
    VklassServiceSensorDescription(
        key="notifications",
        name="Notifications",
        icon="mdi:bell-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (d.get("scoreboard") or {}).get("notifications"),
    ),
)


class VklassServiceSensor(CoordinatorEntity[VklassCoordinator], SensorEntity):
    """Account-level counter, attached to the Vklass service device."""

    _attr_has_entity_name = True
    entity_description: VklassServiceSensorDescription

    def __init__(
        self,
        coordinator: VklassCoordinator,
        entry: VklassConfigEntry,
        description: VklassServiceSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Vklass",
            manufacturer="Vklass",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VklassConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [VklassNewsSensor(coordinator, entry)]
    entities.extend(VklassServiceSensor(coordinator, entry, d) for d in SERVICE_SENSORS)
    for child_name, child in coordinator.data["children"].items():
        descriptions = CHILD_SENSORS
        if child.get("school_id") is not None:
            descriptions = (*CHILD_SENSORS, *GRADE_SENSORS, *COURSE_SENSORS)
        entities.extend(
            VklassChildSensor(coordinator, entry, child_name, description)
            for description in descriptions
        )
    async_add_entities(entities)
