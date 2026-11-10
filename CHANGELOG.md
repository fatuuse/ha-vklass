# Changelog

## 0.1.0-alpha.14

- The Lunch state shows today's lunch until 15:00, then the next day that has a menu. The attribute `date`
  tells which day is shown.

## 0.1.0-alpha.13

- The menu sensor is now `Lunch` (was `Menu days`). Its state is today's lunch, and its attribute `days`
  lists every day with its date, label and items.

## 0.1.0-alpha.12

- Grade entities (merit value and current grades) are always enabled from the start, like holiday,
  gym and course entities.

## 0.1.0-alpha.11

- Holiday confirmation, gym and course entities are always enabled from the start. Their data can appear
  later, so starting them disabled would make them switch from inactive to active over time.

## 0.1.0-alpha.10

- Entities that cannot have data for a child start disabled when they are first created. For example
  attendance for a child without care, grades for a child without a school id, gym for a child without
  gym lessons. Users can enable them. Entities that already exist keep their state.

## 0.1.0-alpha.9

- The config entry is titled "Vklass <username>" for username and password logins.

## 0.1.0-alpha.8

- The settings from Configure are also shown during setup: school ids, calendar categories and hiding
  multi-day all-day events. The school ids are found while setting up, so the choice can be made directly.

## 0.1.0-alpha.7

- New option, off by default: hide all-day events that span several days from the calendar.
  Lessons and gym are not affected.

## 0.1.0-alpha.6

- Entity names are translated. Swedish Home Assistant shows Swedish names, other languages show English.
  Entity ids are created from the name when the entity is first added, so they keep their language later.
- Brand images (icon and logo) added to `custom_components/vklass/brand/`.

## 0.1.0-alpha.5

- Keepalive: the scoreboard is requested every 10 minutes to keep the Vklass session alive.
- A rotated session cookie is saved to the config entry, so it survives restarts.
- An expired session during keepalive starts re-authentication.
- Saving a rotated cookie no longer reloads the integration; only option changes do.

## 0.1.0-alpha.4

- Log in with the Vklass session cookie (`se.vklass.authentication`) as an alternative to username and
  password. The cookie works with BankID and other login methods, because it is copied from a browser.
- The integration no longer logs in on every update. It logs in once and renews the session when it expires.
- Diagnostics also redact the session cookie.

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
