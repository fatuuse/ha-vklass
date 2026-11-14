## 0.2.0

First release on the new version line. It contains all changes from the 0.1.0 alpha series:

- Login with username and password, or with the Vklass session cookie (works with BankID).
- Keepalive against the scoreboard every 10 minutes, saving of a rotated cookie.
- Children found automatically from the welcome page, keyed by student id.
- School ids found automatically, with a choice in setup and under Configure when several are found.
- One calendar per child, with category filter and option to hide multi-day all-day events.
- Sensors: Omsorgstid with a Monday-to-Friday week list, Lunch (today until 15:00, then the next menu day),
  attendance, next lesson with overlapping lessons, merit value, current grades, active courses,
  course attendance, upcoming absences, news, unread messages and notifications.
- Binary sensors: gym today and tomorrow, holiday confirmation needed, absent now.
- Button per child to report an absence for today (disabled by default).
- Entities that cannot have data for a child start disabled.
- Translated entity names and setup/options labels in Swedish and English.
- Diagnostics download without names, ids or credentials.
- Debug logging for logins, session checks and every page fetch, without credentials or ids.

# Changelog

## 0.1.0-alpha.18

- The Omsorgstid sensor has an attribute `week` with Monday to Friday of the current week, each day with
  its date, its times, and whether the child is on leave or the school is closed.
- Debug logs for every page fetch: the path (ids masked), HTTP status and size, plus what was found on the page
  (for example number of children, subjects, absences or calendar events).
- Debug logs for every login outcome: which method was used, why a sign-in failed (including HTTP 200,
  which often means a blocked request), and when a session check triggers a new login. Credentials and
  cookie values are never logged.
- A debug log line per child says whether the care schedule was found, to help diagnose Unknown care states.

## 0.1.0-alpha.17

Seven changes from a code review:

1. Credentials are stripped of surrounding whitespace before validation and storage.
   A pasted trailing newline or space no longer causes "Wrong username or password".
2. A realistic browser User-Agent is sent on every request, so WAF rules that block
   the default python-requests UA do not silently look like wrong credentials.
3. Unexpected parse errors (ValueError / IndexError / AttributeError / KeyError) in
   get_children, parse_care_schedule, parse_grades, parse_courses and parse_absences
   are caught and re-raised as VklassConnectionError with a clear message.
4. _fetch() measures its own wall time and logs it at debug level. A warning is emitted
   if a refresh takes longer than 60 seconds.
5. Per-child entities are removed when a child disappears from the account.
   async_track_child_removal() in entity.py is called by all four platforms.
6. The news sensor's extra_state_attributes caps articles at 10 and truncates intro
   text to 200 characters. A count key is added.
7. async_migrate_entry() stub added so future config schema changes have a home.

## 0.1.0-alpha.16

Found and fixed during a full code review, no new features:

- Fixed: the calendar's `async_get_events` sent Home Assistant's requested date range straight to
  Vklass. Home Assistant can pass this in UTC, which could land on the wrong day near local midnight.
  The range is now converted to local time first.
- Removed dead code in `get_children()` that looked for a grade link on the welcome page. Real welcome
  pages do not contain that link (confirmed against an actual page earlier), so it always matched
  nothing. School ids come entirely from the automatic discovery added in 0.1.0-alpha.7/0.1.0-alpha.8.
- Cosmetic: a formatting defect from an earlier patch glued two entity descriptions together on one
  line in `binary_sensor.py`. It was valid Python and did not change behaviour, but has been cleaned up.
- Removed an unused import in `sensor.py`.

## 0.1.0-alpha.15

- Fixed: the coordinator crashed on every update with `AttributeError: _discovered` (the attribute was set at
  the wrong place). Every update failed, so entities became unavailable.
- Fixed: the Configure dialog returned a 500 error when the integration had not loaded. It now opens, and
  saving keeps the stored school ids.
- Password login starts from an empty cookie jar, so an old session cannot make the login fail.
- Clearer labels: "Auth. method" / "Autentisering metod", calendar categories and multi-day hiding in both languages.

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
