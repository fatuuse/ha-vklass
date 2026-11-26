"""Data coordinator for Vklass.

Three kinds of work:
- a full refresh every UPDATE_INTERVAL (network),
- a presence refresh every PRESENCE_INTERVAL during school start (welcome page and care schedule only),
- a recompute every RECOMPUTE_INTERVAL (no network), so values that depend on the clock (today, the lunch
  switch at 15:00, the week shown on Saturdays, the next lesson) stay right between refreshes.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VklassAuthError, VklassConnectionError, client_for_data
from .const import (
    DATA_COOKIE,
    DOMAIN,
    KEEPALIVE_QUIET_END_HOUR,
    KEEPALIVE_QUIET_START_HOUR,
    OPTION_SCHOOL_IDS,
    UPDATE_INTERVAL,
)
from .summaries import (
    is_presence_window,
    shown_week_monday,
    next_lesson_boundary,
    summarize_absences,
    summarize_calendar,
    summarize_care,
    summarize_courses,
    summarize_grades,
    summarize_menu,
)

_LOGGER = logging.getLogger(__name__)


def _recompute(children: dict[str, dict[str, Any]], now: datetime) -> None:
    """Derive time-dependent values from stored raw data. Makes no network calls."""
    for child in children.values():
        child.update(summarize_calendar(child.get("calendar_events") or [], now))
        child.update(summarize_care(child.get("care_raw") or {}, now.date()))
        child.update(summarize_menu(child.get("food") or {}, now))
        reports = child.get("absence_reports")
        if reports is None:
            child.update(summarize_absences(None, child["id"], now))
        else:
            child.update(summarize_absences({child["id"]: reports}, child["id"], now))


class VklassCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls Vklass for all children, news, scoreboard and school data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client_for_data(entry.data, on_cookie_update=self._on_cookie_update)
        # Options as they were when this coordinator was built. Used to tell option changes from data changes.
        self.applied_options = dict(entry.options)
        self._discovered: dict[int, list[int]] = {}
        self._boundary_unsub = None

    def _on_cookie_update(self, cookie: str) -> None:
        """Called from the executor thread when Vklass rotates the session cookie."""
        self.hass.add_job(self._save_cookie, cookie)

    @callback
    def _save_cookie(self, cookie: str) -> None:
        if self.config_entry.data.get(DATA_COOKIE) == cookie:
            return
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, DATA_COOKIE: cookie}
        )

    def _keepalive_paused(self) -> bool:
        """Password logins sign in again on demand, so keepalive can rest at night. Cookie logins never pause."""
        if DATA_COOKIE in self.config_entry.data:
            return False
        hour = datetime.now().hour
        if KEEPALIVE_QUIET_START_HOUR > KEEPALIVE_QUIET_END_HOUR:
            return hour >= KEEPALIVE_QUIET_START_HOUR or hour < KEEPALIVE_QUIET_END_HOUR
        return KEEPALIVE_QUIET_START_HOUR <= hour < KEEPALIVE_QUIET_END_HOUR

    async def async_keepalive(self, _now: Any = None) -> None:
        """Ping Vklass so the session does not expire from inactivity."""
        if self._keepalive_paused():
            return
        try:
            await self.hass.async_add_executor_job(self.client.ping)
            _LOGGER.debug("Keepalive: scoreboard ping succeeded")
        except VklassAuthError:
            _LOGGER.warning("The Vklass session has expired, re-authentication is needed")
            self.config_entry.async_start_reauth(self.hass)
        except VklassConnectionError as err:
            _LOGGER.debug("Vklass keepalive failed: %s", err)

    async def async_presence_refresh(self, _now: Any = None) -> None:
        """During school start, refresh attendance and care times, and nothing else."""
        if not is_presence_window(datetime.now()) or self.data is None:
            return
        try:
            await self.hass.async_add_executor_job(self._fetch_presence)
        except VklassAuthError:
            _LOGGER.warning("The Vklass session has expired, re-authentication is needed")
            self.config_entry.async_start_reauth(self.hass)
            return
        except VklassConnectionError as err:
            _LOGGER.debug("Presence refresh failed: %s", err)
            return
        _LOGGER.debug("Presence refresh completed")
        self.async_update_listeners()
        self._schedule_next_boundary(self.data["children"])

    async def async_recompute(self, _now: Any = None) -> None:
        """Recompute clock-dependent values from stored data. No network calls."""
        if self.data is None:
            return
        _recompute(self.data["children"], datetime.now())
        self.async_update_listeners()
        self._schedule_next_boundary(self.data["children"])

    def cancel_boundary(self) -> None:
        """Stop the wake-up for the next lesson boundary."""
        if self._boundary_unsub is not None:
            self._boundary_unsub()
            self._boundary_unsub = None

    def _schedule_next_boundary(self, children: dict[str, dict[str, Any]]) -> None:
        """Wake up right after the next lesson starts or ends, so the next lesson sensor changes on time."""
        self.cancel_boundary()
        now = datetime.now()
        when = next_lesson_boundary(children, now)
        if when is None:
            return
        delay = (when - now).total_seconds() + 1
        self._boundary_unsub = async_call_later(self.hass, delay, self._on_boundary)

    @callback
    def _on_boundary(self, _now: Any) -> None:
        self._boundary_unsub = None
        if self.data is None:
            return
        _recompute(self.data["children"], datetime.now())
        self.async_update_listeners()
        self._schedule_next_boundary(self.data["children"])

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.hass.async_add_executor_job(self._fetch)
            self._schedule_next_boundary(data["children"])
            return data
        except VklassAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except VklassConnectionError as err:
            raise UpdateFailed(str(err)) from err

    def _fetch(self) -> dict[str, Any]:
        """Full refresh. Blocking, runs in the executor."""
        _t0 = time.monotonic()
        self.client.ensure_login()
        children = self.client.get_children()
        overrides: dict[str, int] = self.config_entry.options.get(OPTION_SCHOOL_IDS, {})

        # School ids: discovered automatically, kept if found, and overridable in the options flow.
        for child in children.values():
            if child["id"] is None:
                child["school_candidates"] = []
                continue
            if child["id"] not in self._discovered:
                found = self.client.discover_school_ids(child["id"])
                if found:
                    self._discovered[child["id"]] = found
            candidates = set(self._discovered.get(child["id"], []))
            if child["school_id"] is not None:
                candidates.add(child["school_id"])
            child["school_candidates"] = sorted(candidates)

            key = str(child["id"])
            if key in overrides:
                child["school_id"] = int(overrides[key])
            elif child["school_id"] is None and candidates:
                preferred = self._discovered.get(child["id"]) or []
                child["school_id"] = preferred[0] if preferred else min(candidates)

        # A broken care page should not take calendar and news down with it.
        care_error: str | None = None
        try:
            care = self.client.get_care_schedule()
        except VklassConnectionError as err:
            _LOGGER.warning("Could not fetch care schedule: %s", err)
            care = {}
            care_error = str(err)
        self._ensure_shown_week(care)

        try:
            absences: dict[int, list[dict[str, Any]]] | None = self.client.get_absences()
        except VklassConnectionError as err:
            _LOGGER.warning("Could not fetch absences: %s", err)
            absences = None

        now = datetime.now()
        for child in children.values():
            events: list[dict[str, Any]] = []
            if child["id"] is not None:
                events = self.client.get_calendar(child["id"])
            child["calendar_events"] = events
            child["care_raw"] = care.get(child["id"], {})
            child["absence_reports"] = None if absences is None else absences.get(child["id"], [])

            if care_error is not None:
                _LOGGER.debug("Care status for student %s: error: %s", child["id"], care_error)
            elif child["id"] not in care:
                _LOGGER.debug("Care status for student %s: no care schedule found", child["id"])
            else:
                _LOGGER.debug("Care status for student %s: ok", child["id"])

            if child["id"] is not None and child["school_id"] is not None:
                child.update(self._fetch_school_data(child))

        _recompute(children, now)

        try:
            scoreboard = self.client.get_scoreboard()
        except VklassConnectionError as err:
            _LOGGER.warning("Could not fetch scoreboard: %s", err)
            scoreboard = {}

        _elapsed = time.monotonic() - _t0
        _LOGGER.debug("Vklass refresh completed in %.1f s (%d children)", _elapsed, len(children))
        if _elapsed > 60:
            _LOGGER.warning(
                "Vklass refresh took %.0f s. Enable debug logging to see per-step timing.", _elapsed
            )
        return {
            "children": children,
            "news": self.client.get_news(),
            "scoreboard": scoreboard,
        }

    def _fetch_presence(self) -> None:
        """Attendance (welcome page) and care times (care schedule). Blocking, runs in the executor."""
        self.client.ensure_login()
        fresh = self.client.get_children()
        care = self.client.get_care_schedule()
        self._ensure_shown_week(care)
        now = datetime.now()
        for key, child in self.data["children"].items():
            new = fresh.get(key)
            if new is not None:
                child["caretime"] = new["caretime"]
                child["check"] = new["check"]
                child["food"] = new["food"]
            child["care_raw"] = care.get(child["id"], {}) if child["id"] is not None else {}
        _recompute(self.data["children"], now)

    def _ensure_shown_week(self, care: dict[int, dict[str, Any]]) -> None:
        """The overview page covers about four weeks. If the week shown is not in it, load that week too."""
        monday = shown_week_monday(datetime.now().date())
        if any(monday.isoformat() in entry.get("schedule", {}) for entry in care.values()):
            return
        try:
            days = self.client.get_care_days(monday)
        except VklassConnectionError as err:
            _LOGGER.debug("Could not load the care schedule for the shown week: %s", err)
            return
        for student_id, schedule in days.items():
            care.setdefault(student_id, {"holidays": [], "schedule": {}})["schedule"].update(schedule)
        _LOGGER.debug("Care schedule for the shown week loaded from the week view")

    def _fetch_school_data(self, child: dict[str, Any]) -> dict[str, Any]:
        """Grades (grades 7-9 style) and courses (judgements). Either may be missing for a school."""
        data: dict[str, Any] = {}
        try:
            data.update(summarize_grades(self.client.get_grades(child["id"], child["school_id"])))
        except VklassConnectionError as err:
            _LOGGER.debug("No grades for student %s: %s", child["id"], err)
            data.update(summarize_grades({}))
        try:
            data.update(summarize_courses(self.client.get_courses(child["id"], child["school_id"])))
        except VklassConnectionError as err:
            _LOGGER.debug("No courses for student %s: %s", child["id"], err)
            data.update(summarize_courses({}))
        return data
