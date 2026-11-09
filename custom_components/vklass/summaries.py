"""Pure summary helpers.

No Home Assistant imports here, so these functions can be tested without Home Assistant.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .const import GYM_CATEGORY, GYM_KEYWORD, LESSON_CATEGORIES, SESSION_SEPARATOR


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
        if (event.get("code") or "").lower() != GYM_KEYWORD:
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


def summarize_care(care: dict[str, Any], today: date) -> dict[str, Any]:
    """Derive today/tomorrow care times and pending holiday confirmations."""
    schedule: dict[str, dict[str, Any]] = care.get("schedule", {})
    tomorrow = today + timedelta(days=1)
    holidays: list[dict[str, Any]] = care.get("holidays", [])

    return {
        "care_today": _care_state(schedule.get(today.isoformat())),
        "care_tomorrow": _care_state(schedule.get(tomorrow.isoformat())),
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
