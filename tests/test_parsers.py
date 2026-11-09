"""Offline tests for the parsers and summaries.

Only pure code is imported (api.py and summaries.py), so Home Assistant is not needed.
All names, ids and dates are invented test data.
Run with: python3 tests/test_parsers.py   (or: python3 -m pytest tests)
"""
from __future__ import annotations

import html
import importlib
import json
import pathlib
import sys
import types
from datetime import date, datetime, timedelta
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")
summaries = importlib.import_module(f"{PKG}.summaries")

CHILD_A = 111111  # "Test Child A"
CHILD_B = 222222  # "Test Child B"
CHILD_C = 333333  # referenced on the page without a card
SCHOOL = 444444


def _fake_client(page: str) -> "api.VklassClient":
    client = api.VklassClient("user", "pass")
    client._request = lambda method, url, **kw: SimpleNamespace(text=page, status_code=200)
    return client


def _enhanced(component: str, path: str, model: dict, tail: str = "'', '', null") -> str:
    return (f"<script>enhanceServerHtml('{component}', '{path}', "
            f"'{json.dumps(model, ensure_ascii=False)}', {tail})</script>")


def _card(name: str, student_id: int) -> str:
    return ('<div class="vk-student-card">'
            f'<h2 class="vk-student-card-header__text">{name}</h2>'
            f'<a class="vk-link" href="#/Calendar/Schedule?date=2026-11-09&amp;studentIds={student_id}">x</a>'
            '</div>\r\n\t\t\t\t\t\r\n\r\n')


def _event(title, start, end, category="lecture", code="", cancelled=False, location=None):
    return {"title": title, "code": code, "start": start, "end": end, "category": category,
            "cancelled": cancelled, "location": location, "all_day": False, "event_type": None,
            "class_name": "", }


NOW = datetime(2026, 11, 9, 8, 0)


def test_welcome_children_keyed_by_student_id():
    page = (_card("Test Child A", CHILD_A) + _card("Test Child B", CHILD_B)
            + f'<a href="#/Calendar/Schedule?date=2026-11-09&amp;studentIds={CHILD_C}">ref</a>')
    children = _fake_client(page).get_children()
    assert set(children) == {str(CHILD_A), str(CHILD_B), str(CHILD_C)}
    assert children[str(CHILD_A)]["name"] == "Test Child A"
    assert children[str(CHILD_C)]["name"] == f"Student {CHILD_C}"


def test_care_schedule_and_summary():
    model = {
        "childInSchoolItems": [{"student": {"id": CHILD_A}, "schoolId": 9001,
                                "holidayData": {"5001": {"isConfirmed": False}}}],
        "schoolHolidayData": {"9001": [{"holidayId": 5001, "name": "Test holiday",
                                        "startDate": "2026-12-21", "endDate": "2027-01-08",
                                        "confirmationDeadlineDate": "2026-12-07"}]},
        "schoolClosedData": {"9001": ["2026-11-10"]},
        "scheduleData": [
            {"studentId": CHILD_A, "schoolId": 9001, "date": "2026-11-09", "startTime": "08:00",
             "endTime": "16:00", "isOnLeave": False, "message": None},
            {"studentId": CHILD_A, "schoolId": 9001, "date": "2026-11-10", "startTime": "08:00",
             "endTime": "15:30", "isOnLeave": False, "message": None},
            {"studentId": CHILD_A, "schoolId": 9001, "date": "2026-11-11", "startTime": None,
             "endTime": None, "isOnLeave": True, "message": None},
        ],
    }
    page = _enhanced("careschedule-overview", "common/views/careschedule/careschedule-overview",
                     model, "'careScheduleOverviewClientModel', '', null")
    care = api.parse_care_schedule(page)[CHILD_A]
    today = summaries.summarize_care(care, date(2026, 11, 9))
    assert today["care_today"]["state"] == "08:00\u201316:00"
    assert today["care_tomorrow"]["state"] == "Closed"
    assert len(today["pending_holidays"]) == 1
    assert summaries.summarize_care(care, date(2026, 11, 10))["care_tomorrow"]["state"] == "On leave"


def test_grades_use_latest_real_term():
    items = [
        {"subjectName": "Subject A", "gradeTerm3": "B", "gradeTerm4": "A"},
        {"subjectName": "Subject B", "gradeTerm3": "B", "gradeTerm4": "(B)"},
        {"subjectName": "Subject C", "gradeTerm4": "C"},
    ]
    headers = "".join(
        f'<vkau-order-link order-by-property="gradeOrderTerm{i}" text="{t}"></vkau-order-link>'
        for i, t in enumerate(["HT 24", "VT 25", "HT 25", "VT 26", "HT 26"], start=1))
    merit = ('Meritvärde</div>'
             '<div class="vk-flex__item--narrow hidden-phone">-</div>'
             '<div class="vk-flex__item--narrow hidden-phone">-</div>'
             '<div class="vk-flex__item--narrow hidden-phone">-</div>'
             '<div class="vk-flex__item--narrow">290,0</div>'
             '<div class="vk-flex__item--narrow">-</div>'
             '<div id="meritRowDetail"></div>')
    page = headers + merit + _enhanced("results-gradeselementaryschool", "", {"items": items})
    summary = summaries.summarize_grades(api.parse_grades(page))
    assert summary["grade_term"] == "VT 26"
    assert summary["grades_current"] == {"Subject A": "A", "Subject C": "C"}
    assert summary["merit_value"] == 290.0


def test_courses_attendance_school_id_and_empty_input():
    items = [
        {"subjectName": "Subject A", "courseActive": True, "judgement": "Good", "date": "2026-06-09",
         "isPublished": True, "attendancePresentTimePercent": "100 %",
         "criterias": {"totalCriteriasCount": 5, "achievedCriteriasCount": 0}},
        {"subjectName": "Subject B", "courseActive": True, "judgement": None, "date": "0001-01-01",
         "isPublished": False, "attendancePresentTimePercent": "90,5 %",
         "criterias": {"totalCriteriasCount": 6, "achievedCriteriasCount": 0}},
    ]
    parsed = api.parse_courses(_enhanced("studyoverview-courses", "", {"items": items, "schoolId": SCHOOL}))
    assert parsed["school_id"] == SCHOOL
    assert parsed["courses"][1]["judgement_date"] is None
    summary = summaries.summarize_courses(parsed)
    assert summary["courses_active"] == 2
    assert summary["courses_attendance"] == 95.2
    assert summaries.summarize_courses({})["courses_active"] is None


def test_school_id_discovery_and_failure():
    items = [{"subjectName": "Subject A", "courseActive": True, "judgement": None, "date": "0001-01-01",
              "isPublished": False, "attendancePresentTimePercent": "100 %",
              "criterias": {"totalCriteriasCount": 1, "achievedCriteriasCount": 0}}]
    page = _enhanced("studyoverview-courses", "", {"items": items, "schoolId": SCHOOL})
    assert _fake_client(page).discover_school_ids(CHILD_A) == [SCHOOL]

    failing = api.VklassClient("user", "pass")

    def boom(method, url, **kw):
        raise api.VklassConnectionError("not available")

    failing._request = boom
    assert failing.discover_school_ids(CHILD_A) == []


def test_absences_active_now_and_upcoming():
    model = {"absences": [
        {"id": 1, "studentId": CHILD_A, "absenceType": "VALID", "createdBy": "Test Teacher",
         "startDateTime": "2026-10-20 07:02", "endDateTime": "2026-10-20 23:59"},
        {"id": 2, "studentId": CHILD_A, "absenceType": "VALID", "createdBy": "Test Teacher",
         "startDateTime": "2026-11-09 07:00", "endDateTime": "2026-11-09 23:59"},
        {"id": 3, "studentId": CHILD_A, "absenceType": "VALID", "createdBy": "Test Teacher",
         "startDateTime": "2026-11-10 07:00", "endDateTime": "2026-11-10 23:59"},
    ]}
    page = f'<template with.bind="{html.escape(json.dumps(model), quote=True)}"></template>'
    parsed = api.parse_absences(page)
    summary = summaries.summarize_absences(parsed, CHILD_A, datetime(2026, 11, 9, 10, 0))
    assert summary["absent_now"] is True
    assert summary["absences_upcoming"] == 2
    assert summaries.summarize_absences(None, CHILD_A, NOW)["absent_now"] is None


def test_event_type_4_is_a_lesson_but_never_gym():
    now = datetime(2026, 11, 9, 10, 0)
    events = [
        _event("Meeting", "2026-11-09T15:00:00", "2026-11-09T16:00:00", category="event", code="IDH"),
        _event("Gym", "2026-11-10T12:30:00", "2026-11-10T13:10:00", category="lecture", code="IDH"),
    ]
    summary = summaries.summarize_calendar(events, now)
    assert summary["gym_today"] is False
    assert summary["gym_tomorrow"] is True
    assert summary["next_event"]["title"] == "Meeting"


def test_overlapping_lessons_are_joined_with_separator():
    events = [
        _event("Test Lesson A", "2026-11-09T08:15:00", "2026-11-09T09:30:00", code="A"),
        _event("Test Lesson B", "2026-11-09T09:00:00", "2026-11-09T10:00:00", code="B"),
        _event("Test Lesson C", "2026-11-09T11:00:00", "2026-11-09T12:00:00", code="C"),
    ]
    block = summaries.summarize_calendar(events, NOW)["next_event"]
    assert block["title"] == "Test Lesson A | Test Lesson B"
    assert block["conflict"] is True
    assert len(block["events"]) == 2


def test_single_lesson_has_no_separator_and_cancelled_is_ignored():
    events = [
        _event("Test Lesson A", "2026-11-09T08:15:00", "2026-11-09T09:30:00", code="A"),
        _event("Cancelled", "2026-11-09T08:20:00", "2026-11-09T08:40:00", code="X", cancelled=True),
    ]
    block = summaries.summarize_calendar(events, NOW)["next_event"]
    assert block["title"] == "Test Lesson A"
    assert block["conflict"] is False


def test_calendar_request_uses_requested_window_and_categories():
    captured: dict = {}

    def fake(method, url, **kw):
        captured.update(kw.get("data", {}))
        payload = [{"title": "Test Event", "text": "IDH", "start": "2026-11-09 15:00",
                    "end": "2026-11-09 16:00", "eventType": 4, "className": "vk-cl-event-event",
                    "cancelled": False, "allDay": False}]
        return SimpleNamespace(json=lambda: payload, text="", status_code=200)

    client = api.VklassClient("user", "pass")
    client._request = fake
    start = datetime(2026, 11, 9, 0, 0).astimezone()
    end = start + timedelta(days=30)
    events = client.get_calendar(CHILD_A, start, end)
    assert captured["start"] == start.isoformat()
    assert captured["end"] == end.isoformat()
    assert events[0]["category"] == "event"
    assert events[0]["code"] == "IDH"


def test_category_falls_back_to_event_type():
    client = api.VklassClient("user", "pass")
    client._request = lambda method, url, **kw: SimpleNamespace(
        json=lambda: [{"title": "Test Plan", "start": "2026-11-09 00:00", "end": None, "eventType": 16,
                       "className": "", "cancelled": False, "allDay": True}],
        text="", status_code=200)
    events = client.get_calendar(CHILD_A)
    assert events[0]["category"] == "plan"
    assert events[0]["end"] is None


def test_news_window_uses_publish_date():
    today = date.today()
    recent = (today - timedelta(days=1)).isoformat()
    old = (today - timedelta(days=10)).isoformat()
    model = {"newsArticles": [
        {"id": 1, "title": "Recent", "publishDate": recent, "files": [], "children": []},
        {"id": 2, "title": "Old", "publishDate": old, "files": [], "children": []},
    ]}
    page = _enhanced("x", "common/views/shared/display-templates/news-feed-model/news-feed-model", model,
                     "'', '', null")
    news = _fake_client(page).get_news()
    assert [a["title"] for a in news] == ["Recent"]
    assert news[0]["url"].endswith("/Home/News/1")


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
