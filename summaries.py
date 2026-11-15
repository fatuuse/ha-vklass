"""Pure summary helpers.

No Home Assistant imports here, so these functions can be tested without Home Assistant.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any

from .const import (
    GYM_CATEGORY,
    GYM_KEYWORD,
    LESSON_CATEGORIES,
    LESSON_START_RECALC_DELAY,
    PRESENCE_END,
    PRESENCE_START,
    SESSION_SEPARATOR,
)


def _span(event: dict[str, Any]) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"]) if event.get("end") else start + timedelta(hours=1)
    return start, end


def _lesson_block(lessons: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """The next lesson, plus every lesson that overlaps it. Titles are joined with SESSION_SEPARATOR."""
    upcoming = [(event, *_span(event)) for event in lessons if _span(event)[1] > now]
    if not upcoming:
        return None

    first, first_start, first_end = min(upcoming, key=lambda item: item[1])
    group = sorted(
        (item for item in upcoming if item[1] < first_end and item[2] > first_start),
        key=lambda item: item[1],
    )
    return {
        "title": SESSION_SEPARATOR.join(str(e.get("title") or e.get("code") or "") for e, _, _ in group),
        "start": first_start.isoformat(),
        "end": first_end.isoformat(),
        "location": first.get("location"),
        "conflict": len(group) > 1,
        "events": [
            {"title": e.get("title"), "start": s.isoformat(), "end": en.isoformat(), "location": e.get("location")}
            for e, s, en in group
        ],
    }


def summarize_calendar(events: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Gym today/tomorrow (gym lessons only) and the next lesson block.

    Lessons are categories in LESSON_CATEGORIES, which includes calendar events (type 4).
    Gym is a lecture with the gym code, so a type 4 event never counts as gym.
    """
    today = now.date()
    tomorrow = today + timedelta(days=1)
    lessons = [e for e in events if e.get("category") in LESSON_CATEGORIES and not e.get("cancelled")]

    gym_today = False
    gym_tomorrow = False
    for event in events:
        if event.get("category") != GYM_CATEGORY or event.get("cancelled"):
            continue
        if not is_gym(event):
            continue
        day = _span(event)[0].date()
        gym_today = gym_today or day == today
        gym_tomorrow = gym_tomorrow or day == tomorrow

    return {"gym_today": gym_today, "gym_tomorrow": gym_tomorrow, "next_event": _lesson_block(lessons, now)}


def _care_state(entry: dict[str, Any] | None) -> dict[str, Any]:
    """Turn one care schedule day into a state string plus details."""
    if entry is None:
        return {"state": "Unknown"}
    if entry["closed"]:
        state = "Closed"
    elif entry["on_leave"]:
        state = "On leave"
    elif entry["start"] and entry["end"]:
        state = f"{entry['start']}\u2013{entry['end']}"
    else:
        state = "Not scheduled"
    return {
        "state": state,
        "start": entry["start"],
        "end": entry["end"],
        "on_leave": entry["on_leave"],
        "closed": entry["closed"],
        "message": entry["message"],
    }


WEEKDAY_NAMES = ["måndag", "tisdag", "onsdag", "torsdag", "fredag"]


WEEKEND_START = 5  # Saturday


def current_week(schedule: dict[str, dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """Monday to Friday of the week shown.

    The school week ends on Friday. From Saturday on, the week shown is the coming one,
    so the family can prepare for it.
    """
    monday = today - timedelta(days=today.weekday())
    if today.weekday() >= WEEKEND_START:
        monday += timedelta(days=7)
    week = []
    for offset, weekday in enumerate(WEEKDAY_NAMES):
        day = monday + timedelta(days=offset)
        week.append({"date": day.isoformat(), "weekday": weekday,
                     **_care_state(schedule.get(day.isoformat()))})
    return week


def summarize_care(care: dict[str, Any], today: date) -> dict[str, Any]:
    """Derive today/tomorrow care times and pending holiday confirmations."""
    schedule: dict[str, dict[str, Any]] = care.get("schedule", {})
    tomorrow = today + timedelta(days=1)
    holidays: list[dict[str, Any]] = care.get("holidays", [])

    return {
        "care_today": _care_state(schedule.get(today.isoformat())),
        "care_tomorrow": _care_state(schedule.get(tomorrow.isoformat())),
        "care_week": current_week(schedule, today),
        "care_schedule": [
            {"date": day, **_care_state(entry)} for day, entry in sorted(schedule.items())
        ],
        "holidays": holidays,
        "pending_holidays": [h for h in holidays if not h["confirmed"]],
    }


def summarize_grades(grades: dict[str, Any]) -> dict[str, Any]:
    """Pick the latest term with real grades. Grades in parentheses are from an earlier term."""
    terms: list[str] = grades.get("terms", [])
    subjects: dict[str, dict[str, str]] = grades.get("subjects", {})
    merit: dict[str, float] = grades.get("merit", {})

    latest = None
    for term in terms:
        if any(not values[term].startswith("(") for values in subjects.values() if term in values):
            latest = term

    current = {
        subject: values[latest]
        for subject, values in subjects.items()
        if latest in values and not values[latest].startswith("(")
    } if latest else {}

    merit_term = next((t for t in reversed(terms) if t in merit), None)
    return {
        "grade_term": latest,
        "grades_current": current,
        "grades_history": subjects,
        "merit_term": merit_term,
        "merit_value": merit[merit_term] if merit_term else None,
        "merit_history": merit,
    }


def summarize_courses(courses: dict[str, Any]) -> dict[str, Any]:
    """Count active courses and average attendance. Empty input means no data, not zero."""
    items: list[dict[str, Any]] = courses.get("courses", [])
    if not items:
        return {"courses": [], "courses_active": None, "courses_attendance": None}

    active = [c for c in items if c["active"]]
    percents = [c["attendance_percent"] for c in active if c["attendance_percent"] is not None]
    average = round(sum(percents) / len(percents), 1) if percents else None
    return {"courses": items, "courses_active": len(active), "courses_attendance": average}


def summarize_absences(
    absences: dict[int, list[dict[str, Any]]] | None, student_id: int | None, now: datetime
) -> dict[str, Any]:
    """Absence reports for one child. None means the page could not be read, not "no absences"."""
    if absences is None:
        return {"absences": None, "absences_upcoming": None, "absent_now": None}

    items = sorted(absences.get(student_id, []), key=lambda a: a["start"], reverse=True)
    upcoming = [a for a in items if datetime.fromisoformat(a["end"]) >= now]
    absent_now = any(
        datetime.fromisoformat(a["start"]) <= now <= datetime.fromisoformat(a["end"]) for a in items
    )
    return {"absences": items[:20], "absences_upcoming": len(upcoming), "absent_now": absent_now}


def is_multiday_all_day(event: dict[str, Any]) -> bool:
    """True for all-day events that span more than one day, such as a whole term or a plan."""
    if not event.get("all_day") or not event.get("end"):
        return False
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    return end - start > timedelta(days=1)


def _has_care(child: dict[str, Any]) -> bool:
    return bool(child.get("care_schedule") or child.get("caretime") or child.get("check"))


# Entities that only make sense for some children. Everything else is enabled.
ENTITY_RELEVANCE = {
    "care_tomorrow": _has_care,
    "care_time": _has_care,
    "attendance": _has_care,
    "report_absence": lambda child: False,
}


def entity_enabled_by_default(child: dict[str, Any], key: str) -> bool:
    """Whether an entity is enabled when it is first registered.

    Only applies to new entities. Users can enable any entity later in Home Assistant.
    """
    rule = ENTITY_RELEVANCE.get(key)
    return True if rule is None else rule(child)


_WEEKDAYS = {"måndag": 0, "tisdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lördag": 5, "söndag": 6}


def _label_date(label: str, today: date) -> date | None:
    """The date a menu label refers to: Idag, Imorgon, or the next occurrence of a weekday."""
    text = label.strip().lower()
    if text == "idag":
        return today
    if text == "imorgon":
        return today + timedelta(days=1)
    if text in _WEEKDAYS:
        return today + timedelta(days=(_WEEKDAYS[text] - today.weekday()) % 7)
    return None


MENU_SWITCH_TIME = time(15, 0)


def summarize_menu(food: dict[str, list[str]], now: datetime) -> dict[str, Any]:
    """The lunch to show, every day as an attribute.

    Until MENU_SWITCH_TIME the state is today's lunch. From then on it is the next day that has a menu.
    """
    today = now.date()
    days = [
        {"date": day.isoformat() if day else None, "label": label, "items": items}
        for label, items in food.items()
        for day in [_label_date(label, today)]
    ]
    days.sort(key=lambda d: d["date"] or "9999-12-31")

    first_day = today if now.time() < MENU_SWITCH_TIME else today + timedelta(days=1)
    shown = next(
        (d for d in days if d["date"] and d["items"] and date.fromisoformat(d["date"]) >= first_day),
        None,
    )
    return {
        "menu_state": " / ".join(shown["items"]) if shown else None,
        "menu_date": shown["date"] if shown else None,
        "menu_days": days,
    }


def is_presence_window(now: datetime) -> bool:
    """True on weekdays between PRESENCE_START and PRESENCE_END, when attendance is refreshed often."""
    return now.weekday() < 5 and PRESENCE_START <= now.time() < PRESENCE_END


def next_lesson_boundary(children: dict[str, dict[str, Any]], now: datetime) -> datetime | None:
    """The next moment to recalculate: 10 minutes after a lesson starts, or just after it ends.

    Across all children. None if there is no such moment left in the calendar window.
    """
    moments = []
    for child in children.values():
        for event in child.get("calendar_events") or []:
            if event.get("category") not in LESSON_CATEGORIES or event.get("cancelled"):
                continue
            start, end = _span(event)
            for trigger in (start + LESSON_START_RECALC_DELAY, end + timedelta(seconds=1)):
                if trigger > now:
                    moments.append(trigger)
    return min(moments, default=None)


NEWS_ARTICLE_LIMIT = 10
NEWS_INTRO_LIMIT = 200
NEWS_LATEST_TEXT_LIMIT = 4000


def news_attributes(news: list[dict[str, Any]]) -> dict[str, Any]:
    """Attributes for the news sensor.

    `articles` lists the 10 newest articles with a short intro and no body text. `latest_text` is the body
    of the newest article, capped, so an automation can read it and propose calendar events.
    """
    newest_first = sorted(news, key=lambda a: a.get("publish_date") or "", reverse=True)
    articles = []
    for article in newest_first[:NEWS_ARTICLE_LIMIT]:
        entry = {k: v for k, v in article.items() if k != "text"}
        intro = entry.get("intro") or ""
        if len(intro) > NEWS_INTRO_LIMIT:
            entry["intro"] = intro[:NEWS_INTRO_LIMIT] + "\u2026"
        articles.append(entry)
    latest_text = (newest_first[0].get("text") or "") if newest_first else ""
    if len(latest_text) > NEWS_LATEST_TEXT_LIMIT:
        latest_text = latest_text[:NEWS_LATEST_TEXT_LIMIT] + "\u2026"
    return {"count": len(news), "articles": articles, "latest_text": latest_text}


GYM_PATTERN = re.compile(r"\bidh\b|idrott|gympa|\bidr\b")


def is_gym(event: dict[str, Any]) -> bool:
    """A gym lesson: code IDH, or a title that says idrott, gympa or idr. Vklass uses short codes like IDH."""
    text = f"{event.get('title') or ''} {event.get('code') or ''}".lower()
    return bool(GYM_PATTERN.search(text))

