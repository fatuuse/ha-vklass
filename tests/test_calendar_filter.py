"""Offline tests for hiding multi-day all-day events. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_calendar"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

summaries = importlib.import_module(f"{PKG}.summaries")


def _all_day(start: str, end: str | None) -> dict:
    return {"all_day": True, "start": start, "end": end}


def test_term_long_all_day_event_is_multiday():
    assert summaries.is_multiday_all_day(_all_day("2026-08-15T00:00:00", "2027-06-20T00:00:00")) is True


def test_single_day_all_day_event_is_not_multiday():
    assert summaries.is_multiday_all_day(_all_day("2026-11-09T00:00:00", "2026-11-10T00:00:00")) is False


def test_timed_event_is_never_multiday():
    event = {"all_day": False, "start": "2026-11-09T08:00:00", "end": "2026-11-11T09:00:00"}
    assert summaries.is_multiday_all_day(event) is False


def test_all_day_event_without_end_is_not_multiday():
    assert summaries.is_multiday_all_day(_all_day("2026-11-09T00:00:00", None)) is False


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
