"""Calendar platform: one schedule calendar per child."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VklassConfigEntry
from .const import CALENDAR_CATEGORIES, OPTION_CALENDAR_CATEGORIES
from .coordinator import VklassCoordinator
from .entity import VklassChildEntity


def _to_calendar_event(event: dict[str, Any]) -> CalendarEvent:
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"]) if event.get("end") else start + timedelta(hours=1)

    if event.get("all_day"):
        # Home Assistant expects an exclusive end date for all-day events
        start_value = start.date()
        end_value = end.date() if end.time() == time(0) else end.date() + timedelta(days=1)
        if end_value <= start_value:
            end_value = start_value + timedelta(days=1)
    else:
        start_value = start.astimezone()
        end_value = end.astimezone()

    return CalendarEvent(
        summary=event.get("title") or event.get("code") or "",
        start=start_value,
        end=end_value,
        location=event.get("location"),
        description=event.get("category"),
    )


class VklassChildCalendar(VklassChildEntity, CalendarEntity):
    _attr_icon = "mdi:calendar-account"
    _attr_name = "Schedule"

    def __init__(self, coordinator: VklassCoordinator, entry: VklassConfigEntry, child_key: str) -> None:
        super().__init__(coordinator, entry, child_key, "schedule")
        self._entry = entry

    def _allowed(self) -> set[str]:
        return set(self._entry.options.get(OPTION_CALENDAR_CATEGORIES, CALENDAR_CATEGORIES))

    @property
    def event(self) -> CalendarEvent | None:
        """The next event that has not ended yet, from the coordinator's 7-day window."""
        now = datetime.now()
        allowed = self._allowed()
        best: dict[str, Any] | None = None
        for raw in self.child.get("calendar_events") or []:
            if raw["category"] not in allowed or raw["cancelled"]:
                continue
            end = datetime.fromisoformat(raw["end"]) if raw.get("end") else datetime.fromisoformat(raw["start"])
            if end >= now and (best is None or raw["start"] < best["start"]):
                best = raw
        return _to_calendar_event(best) if best else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Events for the range Home Assistant asks for, fetched from Vklass."""
        allowed = self._allowed()
        raw_events = await hass.async_add_executor_job(
            self.coordinator.client.get_calendar, self.child["id"], start_date, end_date
        )
        return [
            _to_calendar_event(e)
            for e in raw_events
            if e["category"] in allowed and not e["cancelled"]
        ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VklassConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        VklassChildCalendar(coordinator, entry, key)
        for key, child in coordinator.data["children"].items()
        if child["id"] is not None
    )
