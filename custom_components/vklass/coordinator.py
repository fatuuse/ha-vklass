"""Data coordinator for Vklass."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VklassAuthError, VklassClient, VklassConnectionError
from .const import DOMAIN, GYM_KEYWORD, LESSON_EVENT_TYPE, OPTION_SCHOOL_IDS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


from .summaries import (
    summarize_absences,
    summarize_calendar,
    summarize_care,
    summarize_courses,
    summarize_grades,
)


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
        self.client = VklassClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        self._discovered: dict[int, list[int]] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except VklassAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except VklassConnectionError as err:
            raise UpdateFailed(str(err)) from err

    def _fetch(self) -> dict[str, Any]:
        """Blocking fetch, runs in the executor."""
        self.client.login()
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
                child["school_id"] = min(candidates)

        # A broken care page should not take calendar and news down with it.
        try:
            care = self.client.get_care_schedule()
        except VklassConnectionError as err:
            _LOGGER.warning("Could not fetch care schedule: %s", err)
            care = {}

        now = datetime.now()
        try:
            absences = self.client.get_absences()
        except VklassConnectionError as err:
            _LOGGER.warning("Could not fetch absences: %s", err)
            absences = None

        for child in children.values():
            events: list[dict[str, Any]] = []
            if child["id"] is not None:
                events = self.client.get_calendar(child["id"])
            child["calendar_events"] = events
            child.update(summarize_calendar(events, now))
            child.update(summarize_care(care.get(child["id"], {}), now.date()))
            child.update(summarize_absences(absences, child["id"], now))

            if child["id"] is not None and child["school_id"] is not None:
                child.update(self._fetch_school_data(child))

        try:
            scoreboard = self.client.get_scoreboard()
        except VklassConnectionError as err:
            _LOGGER.warning("Could not fetch scoreboard: %s", err)
            scoreboard = {}

        return {
            "children": children,
            "news": self.client.get_news(),
            "scoreboard": scoreboard,
        }

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
