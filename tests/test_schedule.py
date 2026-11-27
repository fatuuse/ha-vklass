"""Refresh schedule: 8 hours for the full refresh, 15 minutes during school start, keepalive unchanged,
and a window check that only allows weekdays. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from datetime import datetime, time, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_schedule"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

const = importlib.import_module(f"{PKG}.const")
summaries = importlib.import_module(f"{PKG}.summaries")


def test_full_refresh_is_every_8_hours():
    assert const.UPDATE_INTERVAL == timedelta(hours=8)


def test_keepalive_stays_every_10_minutes():
    assert const.KEEPALIVE_INTERVAL == timedelta(minutes=10)


def test_presence_window_is_weekday_morning():
    assert const.PRESENCE_START == time(7, 0)
    assert const.PRESENCE_END == time(9, 30)
    assert const.PRESENCE_INTERVAL == timedelta(minutes=15)


def test_presence_window_on_a_school_morning():
    assert summaries.is_presence_window(datetime(2026, 11, 9, 7, 30)) is True   # Monday
    assert summaries.is_presence_window(datetime(2026, 11, 13, 8, 59)) is True  # Friday


def test_presence_window_covers_the_afternoon_check_in():
    assert summaries.is_presence_window(datetime(2026, 11, 9, 15, 0)) is True   # Monday 15:00
    assert summaries.is_presence_window(datetime(2026, 11, 13, 16, 59)) is True  # Friday 16:59
    assert summaries.is_presence_window(datetime(2026, 11, 9, 14, 59)) is False
    assert summaries.is_presence_window(datetime(2026, 11, 9, 17, 0)) is False
    assert summaries.is_presence_window(datetime(2026, 11, 14, 16, 0)) is False  # Saturday


def test_presence_window_is_closed_outside_school_start():
    assert summaries.is_presence_window(datetime(2026, 11, 9, 6, 59)) is False
    assert summaries.is_presence_window(datetime(2026, 11, 9, 9, 30)) is False
    assert summaries.is_presence_window(datetime(2026, 11, 14, 8, 0)) is False  # Saturday


def test_recompute_interval_is_once_an_hour():
    assert const.RECOMPUTE_INTERVAL == timedelta(hours=1)


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
