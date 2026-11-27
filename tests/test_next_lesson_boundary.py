"""The next lesson sensor must change right when a lesson starts or ends. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_boundary"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

summaries = importlib.import_module(f"{PKG}.summaries")


def _lesson(start, end, category="lecture", cancelled=False):
    return {"category": category, "cancelled": cancelled, "start": start, "end": end, "title": "Test"}


CHILD = {"calendar_events": [_lesson("2026-11-09T09:00:00", "2026-11-09T10:00:00")]}


def test_before_the_lesson_starts_the_recalculation_is_10_minutes_after_the_start():
    when = summaries.next_lesson_boundary({"a": CHILD}, datetime(2026, 11, 9, 8, 30))
    assert when == datetime(2026, 11, 9, 9, 10)


def test_during_the_first_10_minutes_the_recalculation_is_still_at_10_minutes():
    when = summaries.next_lesson_boundary({"a": CHILD}, datetime(2026, 11, 9, 9, 3))
    assert when == datetime(2026, 11, 9, 9, 10)


def test_after_10_minutes_the_next_recalculation_is_just_after_the_end():
    when = summaries.next_lesson_boundary({"a": CHILD}, datetime(2026, 11, 9, 9, 10, 1))
    assert when == datetime(2026, 11, 9, 10, 0, 1)


def test_cancelled_and_non_lesson_events_are_ignored():
    child = {"calendar_events": [
        _lesson("2026-11-09T09:00:00", "2026-11-09T10:00:00", cancelled=True),
        _lesson("2026-11-09T11:00:00", "2026-11-09T12:00:00", category="plan"),
    ]}
    assert summaries.next_lesson_boundary({"a": child}, datetime(2026, 11, 9, 8, 0)) is None


def test_no_boundary_when_nothing_is_left():
    assert summaries.next_lesson_boundary({"a": CHILD}, datetime(2026, 11, 9, 11, 0)) is None


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
