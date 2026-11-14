"""Calendar platform: one schedule calendar per child."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VklassConfigEntry
from .const import CALENDAR_CATEGORIES, OPTION_CALENDAR_CATEGORIES, OPTION_HIDE_MULTIDAY_ALLDAY
from .summaries import is_multiday_all_day
from .coordinator import VklassCoordinator
from .entity import VklassChildEntity, async_track_child_removal


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
    _attr_translation_key = "schedule"

    def __init__(self, coordinator: VklassCoordinator, entry: VklassConfigEntry, child_key: str) -> None:
        super().__init__(coordinator, entry, child_key, "schedule")
        self._entry = entry

    def _allowed(self) -> set[str]:
        return set(self._entry.options.get(OPTION_CALENDAR_CATEGORIES, CALENDAR_CATEGORIES))

    def _hidden(self, event: dict[str, Any]) -> bool:
        return bool(self._entry.options.get(OPTION_HIDE_MULTIDAY_ALLDAY, False)) and is_multiday_all_day(event)

    @property
    def event(self) -> CalendarEvent | None:
        """The next event that has not ended yet, from the coordinator's 7-day window."""
        now = datetime.now()
        allowed = self._allowed()
        best: dict[str, Any] | None = None
        for raw in self.child.get("calendar_events") or []:
            if raw["category"] not in allowed or raw["cancelled"] or self._hidden(raw):
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
            self.coordinator.client.get_calendar,
            self.child["id"],
            dt_util.as_local(start_date),
            dt_util.as_local(end_date),
        )
        return [
            _to_calendar_event(e)
            for e in raw_events
            if e["category"] in allowed and not e["cancelled"] and not self._hidden(e)
        ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VklassConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities_by_child: dict[str, list] = {
        key: [VklassChildCalendar(coordinator, entry, key)]
        for key, child in coordinator.data["children"].items()
        if child["id"] is not None
    }
    async_add_entities(e for elist in entities_by_child.values() for e in elist)
    async_track_child_removal(coordinator, entry, entities_by_child)
