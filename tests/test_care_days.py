"""The week view (CareSchedule/LoadDays) is plain JSON, and the shown week is Monday to Friday. Invented data."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_care_days"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")
summaries = importlib.import_module(f"{PKG}.summaries")


def _model():
    return {
        "fromDate": "2026-12-14",
        "untilDate": "2027-01-10",
        "scheduleData": [
            {"studentId": 111111, "schoolId": 9001, "date": "2026-12-14", "startTime": "07:45", "endTime": "16:15",
             "isOnLeave": False, "message": "Test message.", "deviationDayCustodianDisplayName": "Test Custodian"},
            {"studentId": 111111, "schoolId": 9001, "date": "2026-12-19", "startTime": None, "endTime": None,
             "isOnLeave": True, "message": None},
        ],
        "schoolClosedData": {"9001": ["2026-12-24"]},
    }


def test_week_days_are_parsed_per_student():
    days = api.parse_care_days(_model())
    assert days[111111]["2026-12-14"]["start"] == "07:45"
    assert days[111111]["2026-12-19"]["on_leave"] is True


def test_only_the_fields_the_integration_uses_are_kept():
    entry = api.parse_care_days(_model())[111111]["2026-12-14"]
    assert set(entry) == {"start", "end", "on_leave", "closed", "message"}
    assert "Test Custodian" not in str(api.parse_care_days(_model()))


def test_closed_days_are_marked():
    model = _model()
    model["scheduleData"].append({"studentId": 111111, "schoolId": 9001, "date": "2026-12-24",
                                  "startTime": None, "endTime": None, "isOnLeave": False, "message": None})
    assert api.parse_care_days(model)[111111]["2026-12-24"]["closed"] is True


def test_shown_week_is_this_week_on_weekdays_and_the_coming_week_from_saturday():
    assert summaries.shown_week_monday(date(2026, 12, 9)) == date(2026, 12, 7)   # Wednesday
    assert summaries.shown_week_monday(date(2026, 12, 12)) == date(2026, 12, 14)  # Saturday
    assert summaries.shown_week_monday(date(2026, 12, 13)) == date(2026, 12, 14)  # Sunday


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
