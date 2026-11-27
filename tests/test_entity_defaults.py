"""Offline tests for which entities start enabled. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_defaults"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

summaries = importlib.import_module(f"{PKG}.summaries")
enabled = summaries.entity_enabled_by_default


def _school_only_child() -> dict:
    """A child with lessons and a school, but no care schedule and no grades."""
    return {"care_schedule": [], "caretime": None, "check": None, "grades_history": {},
            "courses": [], "holidays": [], "calendar_events": []}


def test_attendance_is_disabled_for_a_child_without_care():
    child = _school_only_child()
    assert enabled(child, "attendance") is False
    assert enabled(child, "care_time") is False


def test_attendance_is_enabled_for_a_child_with_care():
    child = _school_only_child()
    child["check"] = "Utcheckad (16:12)"
    assert enabled(child, "attendance") is True


def test_grade_entities_are_enabled_only_when_the_child_has_grades():
    child = _school_only_child()
    for key in ["merit_value", "current_grades"]:
        assert enabled(child, key) is False, key
    child["grade_term"] = "HT 25"
    child["merit_value"] = 230.0
    for key in ["merit_value", "current_grades"]:
        assert enabled(child, key) is True, key


def test_holiday_gym_and_course_entities_are_always_enabled():
    child = _school_only_child()
    child["courses"] = [{"name": "Test course"}]
    child["courses_active"] = 1
    for key in ["holiday_confirmation", "idrott_today", "idrott_tomorrow", "courses_active", "course_attendance"]:
        assert enabled(child, key) is True, key


def test_calendar_and_general_entities_are_always_enabled():
    child = _school_only_child()
    for key in ["schedule", "next_lesson", "menu_days", "absent_now", "absences_upcoming", "news"]:
        assert enabled(child, key) is True, key


def test_absence_button_stays_disabled():
    assert enabled(_school_only_child(), "report_absence") is False


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")


def test_grade_and_course_sensors_are_disabled_until_the_child_has_data():
    from types import SimpleNamespace  # noqa: F401  (kept local to the test)
    child = {"grade_term": None, "merit_value": None, "courses": [], "courses_active": None}
    assert enabled(child, "merit_value") is False
    assert enabled(child, "current_grades") is False
    assert enabled(child, "courses_active") is False
    assert enabled(child, "course_attendance") is False
    child_with_grades = {"grade_term": "HT 25", "merit_value": 230.0, "courses": [], "courses_active": 0}
    assert enabled(child_with_grades, "merit_value") is True
    assert enabled(child_with_grades, "current_grades") is True

