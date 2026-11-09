# Changelog

## 0.1.0-alpha.3

- New button per child, `Report absence today`. It is disabled by default and must be enabled
  in the entity settings. It reports an absence from now until 23:59 and checks that Vklass
  shows the report afterwards. It does nothing if an absence already covers the current time.

## 0.1.0-alpha.2

- School ids are discovered automatically. If several are found, the options flow lets you choose.
- One calendar entity per child (`calendar`), with categories selectable in the options flow.
- Calendar events (type 4) count as lessons for the next-lesson sensor, but never as gym.
- Overlapping lessons are shown in the next-lesson sensor, joined with ` | `.
- Calendar requests take a time window, so Home Assistant can ask for any date range.
- Shared client access is locked, so the calendar and the coordinator can run at the same time.

## 0.1.0-alpha.1

First alpha release.

- Config flow with login validation, re-authentication and an options flow for elementary school ids.
- Coordinator polling every 30 minutes, children keyed by student id, entities named after the child.
- Sensors: care today/tomorrow, attendance, next lesson, lunch menu, merit value, current grades,
  active courses, course attendance, upcoming absences, news, unread messages, notifications.
- Binary sensors: gym today/tomorrow, holiday confirmation needed, absent now.
- Diagnostics download without names, ids or credentials.
- Read-only: absences can be read but not reported.
