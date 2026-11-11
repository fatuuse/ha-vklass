"""Client for the (unofficial) Vklass web endpoints."""
from __future__ import annotations

import html
import json
import logging
import re
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

import requests

from .const import (
    BASE_URL,
    ABSENCE_URL,
    AUTH_COOKIE,
    CONF_AUTH_METHOD,
    COOKIE_DOMAIN,
    COOKIE_NAME,
    DATA_COOKIE,
    DATA_PASSWORD,
    DATA_USERNAME,
    CALENDAR_DAYS,
    CATEGORY_BY_CLASS,
    CATEGORY_BY_EVENT_TYPE,
    CARE_URL,
    CALENDAR_URL,
    HOME_URL,
    LOGIN_PAGE,
    LOGIN_SIGNIN,
    NEWS_DAYS,
    NEWS_URL,
    REQUEST_TIMEOUT,
    SCOREBOARD_URL,
)

_LOGGER = logging.getLogger(__name__)

TOKEN_RE = re.compile(r'<input name="__RequestVerificationToken" type="hidden" value="([^"]*)" />')
CHILD_CARD_RE = re.compile(
    r'<div class="vk-student-card">([\s\S.]*?)'
    r'(?:</div>\r\n\t\t\t\t\t\r\n\r\n|</div>\r\n\t\t\t</vkau-swipe>)'
)
NAME_RE = re.compile(r"<h2.*>(.*?)</h2>")
CARETIME_RE = re.compile(
    r'<a class="vk-link" href="#/CareSchedule/Overview">.*?<span class="vk-link__text">(.*?)</span>'
)
CHECK_RE = re.compile(r'<div class="vk-flex vk-flex--v-align-center">.*<span class="text-bold">(.*?)</span>.*</div>')
ID_RE = re.compile(r'<a class="vk-link" href="#/Calendar/Schedule\?date=.*&amp;studentIds=(.*?)">')
FOOD_RE = re.compile(r'<div class="vk-student-card__day" (?:[^>]*)><h3>([^>]*)</h3>.*?(?=<ul)(.*?(?=</div>))')
LI_RE = re.compile(r"<li>(.*?)</li>")
TAG_RE = re.compile(r"<[^>]+>")
NEWS_RE = re.compile(r"news-feed-model', '(\{.*?\})', '")


class VklassAuthError(Exception):
    """Wrong username or password."""


class VklassConnectionError(Exception):
    """Vklass could not be reached or returned unexpected data."""


def _parse_food(block: str) -> dict[str, list[str]]:
    """Return {day header: [menu items]} for one child card."""
    menu: dict[str, list[str]] = {}
    for day, body in FOOD_RE.findall(block):
        items = [html.unescape(TAG_RE.sub("", li)).strip() for li in LI_RE.findall(body)]
        menu[html.unescape(day).strip()] = [item for item in items if item]
    return menu


class VklassClient:
    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        cookie: str | None = None,
        on_cookie_update: Callable[[str], None] | None = None,
    ) -> None:
        """Use username and password, or a Vklass session cookie. Never both.

        on_cookie_update is called with the new value when Vklass rotates the cookie.
        """
        self._username = username
        self._password = password
        self._cookie = cookie
        self._on_cookie_update = on_cookie_update
        self._session = requests.Session()
        self._lock = threading.RLock()
        self._authenticated = False
        if cookie is not None:
            self._session.cookies.set(COOKIE_NAME, cookie, domain=COOKIE_DOMAIN, path="/")
            self._authenticated = True

    def login(self) -> None:
        with self._lock:
            self._login()

    def ensure_login(self) -> None:
        """Log in only if no session is known to be active. Expired sessions are renewed on demand."""
        with self._lock:
            if not self._authenticated:
                self._login()

    def _login(self) -> None:
        if self._cookie is not None:
            # Cookie sessions cannot be renewed here. An expired cookie is reported as an auth error.
            self._authenticated = True
            return
        try:
            self._session.cookies.clear()
            page = self._session.get(LOGIN_PAGE, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as err:
            raise VklassConnectionError(str(err)) from err
        if page.status_code != 200:
            raise VklassConnectionError(f"Login page returned HTTP {page.status_code}")

        token = TOKEN_RE.search(page.text)
        if token is None:
            raise VklassConnectionError("Verification token not found on login page")

        try:
            response = self._session.post(
                LOGIN_SIGNIN,
                data={
                    "__RequestVerificationToken": token.group(1),
                    "Username": self._username,
                    "Password": self._password,
                    "RememberMe": "false",
                },
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as err:
            raise VklassConnectionError(str(err)) from err

        if response.status_code == 302:
            _LOGGER.debug("Logged in to Vklass")
            self._authenticated = True
            return
        if response.status_code == 200:
            raise VklassAuthError("Wrong username or password")
        raise VklassConnectionError(f"Login returned HTTP {response.status_code}")

    def _request(self, method: str, url: str, *, retry: bool = True, **kwargs: Any) -> requests.Response:
        with self._lock:
            return self._request_unlocked(method, url, retry=retry, **kwargs)

    def _request_unlocked(self, method: str, url: str, *, retry: bool = True, **kwargs: Any) -> requests.Response:
        try:
            response = self._session.request(
                method, url, allow_redirects=False, timeout=REQUEST_TIMEOUT, **kwargs
            )
        except requests.RequestException as err:
            raise VklassConnectionError(str(err)) from err

        if response.status_code != 200:
            # Session most likely expired (redirect to login). Log in once and retry.
            if retry and response.status_code in (302, 401, 403):
                _LOGGER.debug("Vklass session expired, logging in again")
                self.login()
                return self._request(method, url, retry=False, **kwargs)
            if response.status_code in (302, 401, 403) and self._cookie is not None:
                raise VklassAuthError("The Vklass session cookie has expired")
            raise VklassConnectionError(f"{url} returned HTTP {response.status_code}")
        self._sync_cookie()
        return response

    def get_children(self) -> dict[str, dict[str, Any]]:
        """Return children from the welcome page, keyed by student id as a string.

        Every student id referenced on the page belongs to the account. Ids without
        a readable card get a placeholder name, so they still get their data.
        """
        page = self._request("GET", HOME_URL).text
        grade_links = {int(s): int(school) for s, school in GRADES_LINK_RE.findall(page)}
        children: dict[str, dict[str, Any]] = {}

        for block in CHILD_CARD_RE.findall(page):
            block = block.replace("\r\n", "").replace("\t", "")
            names = NAME_RE.findall(block)
            ids = ID_RE.findall(block)
            student_id = int(ids[0]) if ids and ids[0].isdigit() else None
            if not names or student_id is None:
                _LOGGER.debug("Skipping a welcome card without name or student id")
                continue
            caretime = CARETIME_RE.findall(block)
            check = CHECK_RE.findall(block)
            children[str(student_id)] = {
                "name": html.unescape(names[0]).strip(),
                "id": student_id,
                "school_id": grade_links.get(student_id),
                "caretime": caretime[0].replace("&#x2013;", "-").replace(" ", "") if caretime else None,
                "check": html.unescape(check[0]) if check else None,
                "food": _parse_food(block),
            }

        for student_id in sorted({int(s) for s in STUDENT_IDS_RE.findall(page)}):
            key = str(student_id)
            if key in children:
                continue
            _LOGGER.info("A child was referenced on the welcome page without a card")
            children[key] = {
                "name": f"Student {student_id}",
                "id": student_id,
                "school_id": grade_links.get(student_id),
                "caretime": None,
                "check": None,
                "food": {},
            }

        _LOGGER.debug("Found %d children on the welcome page", len(children))
        return children

    def get_news(self) -> list[dict[str, Any]]:
        """Return news articles published within the last NEWS_DAYS days."""
        page = self._request("GET", NEWS_URL).text
        match = NEWS_RE.search(page)
        if match is None:
            _LOGGER.warning("Could not find news data on Vklass news page")
            return []

        try:
            data = json.loads(match.group(1))
        except ValueError:
            _LOGGER.warning("Could not decode news JSON from Vklass")
            return []

        cutoff = (datetime.today() - timedelta(days=NEWS_DAYS)).date()
        news: list[dict[str, Any]] = []
        for article in data.get("newsArticles", []):
            try:
                published = datetime.strptime(article["publishDate"], "%Y-%m-%d").date()
            except (KeyError, TypeError, ValueError):
                continue
            if published <= cutoff:
                continue
            news.append({
                "id": article.get("id"),
                "url": f"{BASE_URL}/Home/News/{article['id']}" if article.get("id") else None,
                "title": article.get("title"),
                "publish_date": article.get("publishDate"),
                "author": article.get("authorName"),
                "intro": article.get("introText"),
                "tags": article.get("tags"),
                "files": len(article.get("files") or []),
                "children": [c.get("name") for c in article.get("children") or []],
            })
        return news

    def get_calendar(
        self, student_id: int, start: datetime | None = None, end: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Return events for one student in a time window.

        Defaults to midnight today plus CALENDAR_DAYS. Times are sent with the local UTC offset.
        """
        if start is None:
            start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        if end is None:
            end = start + timedelta(days=CALENDAR_DAYS)

        response = self._request(
            "POST",
            CALENDAR_URL,
            data={"students": student_id, "start": start.isoformat(), "end": end.isoformat()},
            headers={"Accept": "text/html"},
        )
        try:
            payload = response.json()
        except ValueError as err:
            raise VklassConnectionError("Calendar response was not JSON") from err

        def to_iso(value: Any) -> str | None:
            # Vklass sends "YYYY-MM-DD HH:MM", or null for open-ended items
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M").isoformat()
            except (TypeError, ValueError):
                return None

        events: list[dict[str, Any]] = []
        for raw in payload:
            start_iso = to_iso(raw.get("start"))
            if start_iso is None:
                continue
            class_name = raw.get("className") or ""
            events.append({
                "title": raw.get("title"),
                "code": html.unescape(TAG_RE.sub("", raw.get("text") or "")).strip(),
                "start": start_iso,
                "end": to_iso(raw.get("end")),
                "event_type": raw.get("eventType"),
                "class_name": class_name,
                "category": CATEGORY_BY_CLASS.get(class_name)
                or CATEGORY_BY_EVENT_TYPE.get(raw.get("eventType"), "other"),
                "location": raw.get("location") or None,
                "cancelled": bool(raw.get("cancelled")),
                "all_day": bool(raw.get("allDay")),
            })
        return events

    def get_care_schedule(self) -> dict[int, dict[str, Any]]:
        """Return care schedule and holidays per student id."""
        page = self._request("GET", CARE_URL).text
        return parse_care_schedule(page)

    def get_grades(self, student_id: int, school_id: int) -> dict[str, Any]:
        """Return grades per subject and term, plus merit values, for one student."""
        page = self._request(
            "GET",
            f"{BASE_URL}/StudyOverview/Grades/{student_id}",
            params={"school": school_id, "X-Requested-With": "XMLHttpRequest"},
        ).text
        return parse_grades(page)

    def get_courses(self, student_id: int, school_id: int | None = None) -> dict[str, Any]:
        """Return subjects with judgements, attendance and criteria for one student.

        Without school_id the server picks the student's school, which is how school ids are discovered.
        """
        params: dict[str, Any] = {"X-Requested-With": "XMLHttpRequest"}
        if school_id is not None:
            params["school"] = school_id
        page = self._request("GET", f"{BASE_URL}/StudyOverview/Courses/{student_id}", params=params).text
        return parse_courses(page)

    def discover_school_ids(self, student_id: int) -> list[int]:
        """Return the school id(s) the student's courses belong to. Empty if none can be read."""
        try:
            school_id = self.get_courses(student_id).get("school_id")
        except VklassConnectionError:
            return []
        return [int(school_id)] if school_id else []

    def report_absence_today(self, student_id: int, now: datetime) -> str:
        """Report an absence for one child from now until the end of the day.

        Returns "reported" or "already_absent". Raises VklassConnectionError when the form
        cannot be used or when Vklass does not show the new report afterwards, so the caller
        never assumes success.
        """
        page = self._request("GET", ABSENCE_URL).text
        if _covers(parse_absences(page), student_id, now):
            return "already_absent"

        token = TOKEN_RE.search(page)
        if token is None:
            raise VklassConnectionError("Absence form token not found")
        minimum = _hidden_value(page, "Notify_MinimumStartDateTime")
        maximum = _hidden_value(page, "Notify_MaximumEndDateTime")

        window_min = datetime.strptime(minimum, "%Y-%m-%d %H:%M:%S") if minimum else now
        window_max = datetime.strptime(maximum, "%Y-%m-%d %H:%M:%S") if maximum else None
        start = max(now.replace(second=0, microsecond=0), window_min)
        end = now.replace(hour=23, minute=59, second=0, microsecond=0)
        if start.date() != now.date() or (window_max is not None and end > window_max):
            raise VklassConnectionError("The absence window for today is closed")

        self._request(
            "POST",
            f"{BASE_URL}/Absence/Notify",
            data={
                "__RequestVerificationToken": token.group(1),
                "Notify.FormOnly": "False",
                "Notify.MinimumStartDateTime": minimum or "",
                "Notify.MaximumEndDateTime": maximum or "",
                "Notify.QuickOptionDate": "",
                "Notify.QuickOptionDateIsNull": "True",
                "Notify.StartDate": start.strftime("%Y-%m-%d"),
                "Notify.StartTime": start.strftime("%H:%M"),
                "Notify.EndDate": end.strftime("%Y-%m-%d"),
                "Notify.EndTime": end.strftime("%H:%M"),
                "Notify.SelectedStudentIds": str(student_id),
            },
        )

        confirmed = parse_absences(self._request("GET", ABSENCE_URL).text)
        if not _covers(confirmed, student_id, now):
            raise VklassConnectionError("Vklass did not confirm the absence report")
        return "reported"

    def _sync_cookie(self) -> None:
        """Pick up a rotated session cookie from the response and tell the owner about it."""
        if self._cookie is None:
            return
        values = [c.value for c in self._session.cookies if c.name == COOKIE_NAME]
        if values and values[-1] != self._cookie:
            self._cookie = values[-1]
            if self._on_cookie_update is not None:
                self._on_cookie_update(self._cookie)

    def ping(self) -> None:
        """Keep the session alive. Uses the scoreboard, which the Vklass start page polls too."""
        self.get_scoreboard()

    def get_absences(self) -> dict[int, list[dict[str, Any]]]:
        """Return current and upcoming absence reports per student id (read-only)."""
        page = self._request("GET", ABSENCE_URL).text
        return parse_absences(page)

    def get_scoreboard(self) -> dict[str, Any]:
        """Return unread counters, e.g. {"notifications": 0, "messages": 0}."""
        response = self._request(
            "GET",
            SCOREBOARD_URL,
            params={"X-Requested-With": "XMLHttpRequest", "_": int(datetime.now().timestamp() * 1000)},
        )
        try:
            data = response.json()
        except ValueError as err:
            # A login page instead of JSON means the session has expired
            raise VklassAuthError("Scoreboard did not return JSON; the session has probably expired") from err
        if not isinstance(data, dict):
            raise VklassConnectionError("Unexpected scoreboard format")
        return data


# The care schedule overview page has no JSON endpoint we use, but it embeds
# its full view model as a JSON string passed to enhanceServerHtml().
CARE_JSON_RE = re.compile(
    r"enhanceServerHtml\('careschedule-overview',.*?,\s*'(\{.*\})',\s*'careScheduleOverviewClientModel'",
    re.S,
)


def parse_care_schedule(page: str) -> dict[int, dict[str, Any]]:
    """Parse the embedded view model of the care schedule overview page."""
    match = CARE_JSON_RE.search(page)
    if match is None:
        raise VklassConnectionError("Care schedule data not found on overview page")
    try:
        model = json.loads(match.group(1))
    except ValueError as err:
        raise VklassConnectionError("Could not decode care schedule data") from err

    closed_by_school = {int(k): set(v) for k, v in (model.get("schoolClosedData") or {}).items()}
    holidays_by_school = {int(k): v for k, v in (model.get("schoolHolidayData") or {}).items()}

    children: dict[int, dict[str, Any]] = {}
    for item in model.get("childInSchoolItems") or []:
        student_id = item["student"]["id"]
        school_id = item["schoolId"]
        holiday_state = item.get("holidayData") or {}

        holidays = []
        for holiday in holidays_by_school.get(school_id, []):
            key = str(holiday.get("holidayId"))
            if key in holiday_state:
                holidays.append({
                    "name": holiday.get("name"),
                    "start": holiday.get("startDate"),
                    "end": holiday.get("endDate"),
                    "confirm_by": holiday.get("confirmationDeadlineDate"),
                    "confirmed": bool(holiday_state[key].get("isConfirmed")),
                })
        children[student_id] = {"holidays": holidays, "schedule": {}}

    for day in model.get("scheduleData") or []:
        student_id = day.get("studentId")
        if student_id not in children:
            continue
        date_str = day["date"]
        children[student_id]["schedule"][date_str] = {
            "start": day.get("startTime"),
            "end": day.get("endTime"),
            "on_leave": bool(day.get("isOnLeave")),
            "closed": date_str in closed_by_school.get(day.get("schoolId"), set()),
            "message": (day.get("message") or "").strip() or None,
        }
    return children


GRADES_LINK_RE = re.compile(r"StudyOverview/Grades/(\d+)\?school=(\d+)")
GRADES_JSON_RE = re.compile(r"enhanceServerHtml\('results-gradeselementaryschool',.*?'(\{.*?\})',\s*'", re.S)
TERM_HEADER_RE = re.compile(r'order-by-property="gradeOrderTerm(\d)" text="([^"]*)"')
MERIT_ROW_RE = re.compile(r"Meritvärde</div>(.*?)meritRowDetail", re.S)
MERIT_CELL_RE = re.compile(r'vk-flex__item--narrow[^"]*">([^<]*)</div>')


def parse_grades(page: str) -> dict[str, Any]:
    """Parse grades and merit values from the elementary school grades view model."""
    match = GRADES_JSON_RE.search(page)
    if match is None:
        raise VklassConnectionError("Grades data not found")
    try:
        model = json.loads(match.group(1))
    except ValueError as err:
        raise VklassConnectionError("Could not decode grades data") from err

    # Term labels come from the column headers, gradeTerm1..5 in chronological order
    header_labels = {int(n): html.unescape(text) for n, text in TERM_HEADER_RE.findall(page)}
    labels = [header_labels.get(i, f"Term {i}") for i in range(1, 6)]

    subjects: dict[str, dict[str, str]] = {}
    for item in model.get("items") or []:
        grades = {}
        for i, label in enumerate(labels, start=1):
            value = (item.get(f"gradeTerm{i}") or "").strip()
            if value:
                grades[label] = value
        subjects[item["subjectName"]] = grades

    merit: dict[str, float] = {}
    row = MERIT_ROW_RE.search(page)
    if row:
        for label, value in zip(labels, MERIT_CELL_RE.findall(row.group(1))):
            value = value.strip()
            if value and value != "-":
                try:
                    merit[label] = float(value.replace(",", "."))
                except ValueError:
                    pass

    return {"terms": labels, "subjects": subjects, "merit": merit}


COURSES_JSON_RE = re.compile(r"enhanceServerHtml\('studyoverview-courses',.*?'(\{.*?\})',\s*'", re.S)


def _percent(value: Any) -> float | None:
    """Turn "100 %" into 100.0."""
    if not value:
        return None
    digits = re.sub(r"[^\d,.]", "", str(value)).replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


def parse_courses(page: str) -> dict[str, Any]:
    """Parse the study overview courses view model (judgements, attendance, criteria)."""
    match = COURSES_JSON_RE.search(page)
    if match is None:
        raise VklassConnectionError("Courses data not found")
    try:
        model = json.loads(match.group(1))
    except ValueError as err:
        raise VklassConnectionError("Could not decode courses data") from err

    courses: list[dict[str, Any]] = []
    for item in (model.get("items") or []) + (model.get("inactiveItems") or []):
        criterias = item.get("criterias") or {}
        judgement = item.get("judgement") or None
        date_str = item.get("date")
        courses.append({
            "subject": item.get("subjectName"),
            "active": bool(item.get("courseActive")),
            "judgement": judgement,
            # Vklass uses 0001-01-01 as "no date"
            "judgement_date": date_str if judgement and date_str and not date_str.startswith("0001") else None,
            "judgement_author": item.get("judgementAuthorFullName"),
            "published": bool(item.get("isPublished")),
            "attendance_percent": _percent(item.get("attendancePresentTimePercent")),
            "criteria_achieved": criterias.get("achievedCriteriasCount"),
            "criteria_total": criterias.get("totalCriteriasCount"),
        })
    return {"courses": courses, "school_id": model.get("schoolId")}


# The absence page embeds its list as an HTML-escaped JSON object in a template attribute.
ABSENCE_JSON_RE = re.compile(r'with\.bind="(\{&quot;absences&quot;.*?\})">')


def parse_absences(page: str) -> dict[int, list[dict[str, Any]]]:
    """Parse absence reports from the absence notify page, grouped by student id."""
    match = ABSENCE_JSON_RE.search(page)
    if match is None:
        raise VklassConnectionError("Absence data not found")
    try:
        model = json.loads(html.unescape(match.group(1)))
    except ValueError as err:
        raise VklassConnectionError("Could not decode absence data") from err

    result: dict[int, list[dict[str, Any]]] = {}
    for raw in model.get("absences") or []:
        try:
            start = datetime.strptime(raw["startDateTime"], "%Y-%m-%d %H:%M").isoformat()
            end = datetime.strptime(raw["endDateTime"], "%Y-%m-%d %H:%M").isoformat()
        except (KeyError, TypeError, ValueError):
            continue
        result.setdefault(raw.get("studentId"), []).append({
            "id": raw.get("id"),
            "start": start,
            "end": end,
            "type": raw.get("absenceType"),
            "created": raw.get("created"),
            "created_by": raw.get("createdBy"),
        })
    return result


STUDENT_IDS_RE = re.compile(r"studentIds=(\d+)")


def _hidden_value(page: str, element_id: str) -> str | None:
    """Value of a hidden form input, found by its id."""
    match = re.search(rf'id="{re.escape(element_id)}" name="[^"]*" value="([^"]*)"', page)
    return match.group(1) if match else None


def _covers(absences: dict[int, list[dict[str, Any]]], student_id: int, now: datetime) -> bool:
    """True if an absence report for the student is active at this moment."""
    return any(
        datetime.fromisoformat(a["start"]) <= now <= datetime.fromisoformat(a["end"])
        for a in absences.get(student_id, [])
    )


def client_for_data(
    data: Mapping[str, Any],
    on_cookie_update: Callable[[str], None] | None = None,
) -> VklassClient:
    """Build a client from config entry data, using either a cookie or username and password."""
    if data.get(CONF_AUTH_METHOD) == AUTH_COOKIE:
        return VklassClient(cookie=data[DATA_COOKIE], on_cookie_update=on_cookie_update)
    return VklassClient(data[DATA_USERNAME], data[DATA_PASSWORD])
