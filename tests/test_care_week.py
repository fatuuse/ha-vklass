"""Tests for the current-week care list and the care status. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_care_week"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

summaries = importlib.import_module(f"{PKG}.summaries")

# 2026-11-11 is a Wednesday, so the week is Monday 2026-11-09 to Friday 2026-11-13
WEDNESDAY = date(2026, 11, 11)


def _entry(start, end):
    return {"start": start, "end": end, "on_leave": False, "closed": False, "message": None}


def test_week_is_monday_to_friday_with_times():
    schedule = {
        "2026-11-09": _entry("07:45", "16:15"),
        "2026-11-10": _entry("07:45", "16:00"),
        "2026-11-11": _entry("07:45", "16:30"),
    }
    week = summaries.current_week(schedule, WEDNESDAY)
    assert [d["weekday"] for d in week] == ["måndag", "tisdag", "onsdag", "torsdag", "fredag"]
    assert [d["date"] for d in week] == ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]
    assert week[0]["state"] == "07:45\u201316:15"
    assert week[0]["start"] == "07:45" and week[0]["end"] == "16:15"
    assert week[3]["state"] == "Unknown"


def test_weekend_is_not_in_the_week_list():
    sunday = date(2026, 11, 15)
    week = summaries.current_week({}, sunday)
    assert week[-1]["weekday"] == "fredag"
    assert len(week) == 5


def test_on_saturday_the_week_shown_is_the_coming_week():
    saturday = date(2026, 11, 14)
    week = summaries.current_week({}, saturday)
    assert [d["date"] for d in week] == ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]


def test_on_sunday_the_week_shown_is_also_the_coming_week():
    sunday = date(2026, 11, 15)
    week = summaries.current_week({}, sunday)
    assert week[0]["date"] == "2026-11-16"
    assert week[-1]["date"] == "2026-11-20"


def test_summary_includes_the_week():
    summary = summaries.summarize_care({"schedule": {}, "holidays": []}, WEDNESDAY)
    assert len(summary["care_week"]) == 5


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
