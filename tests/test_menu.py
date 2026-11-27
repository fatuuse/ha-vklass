"""Offline tests for the lunch menu summary. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_menu"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

summaries = importlib.import_module(f"{PKG}.summaries")

# 2026-11-09 is a Monday
MORNING = datetime(2026, 11, 9, 10, 0)
AFTERNOON = datetime(2026, 11, 9, 15, 0)


def test_before_15_the_state_is_todays_lunch_and_joins_the_options():
    food = {"Idag": ["Test dish A", "Test dish B"], "Imorgon": ["Test dish C"]}
    summary = summaries.summarize_menu(food, MORNING)
    assert summary["menu_state"] == "Test dish A / Test dish B"
    assert summary["menu_date"] == "2026-11-09"


def test_from_15_the_state_is_tomorrows_lunch():
    food = {"Idag": ["Test dish A"], "Imorgon": ["Test dish C"]}
    summary = summaries.summarize_menu(food, AFTERNOON)
    assert summary["menu_state"] == "Test dish C"
    assert summary["menu_date"] == "2026-11-10"


def test_from_15_on_friday_the_state_is_the_next_menu_day():
    friday = datetime(2026, 11, 13, 16, 0)
    food = {"fredag": ["Test dish F"], "onsdag": ["Test dish W"]}
    summary = summaries.summarize_menu(food, friday)
    assert summary["menu_state"] == "Test dish W"
    assert summary["menu_date"] == "2026-11-18"


def test_from_15_with_no_later_menu_the_state_is_empty():
    friday = datetime(2026, 11, 13, 16, 0)
    food = {"fredag": ["Test dish F"]}
    summary = summaries.summarize_menu(food, friday)
    assert summary["menu_state"] is None
    assert summary["menu_date"] is None


def test_weekday_labels_get_the_next_matching_date():
    food = {"Idag": ["A"], "Imorgon": ["B"], "onsdag": ["C"], "fredag": ["D"]}
    days = summaries.summarize_menu(food, MORNING)["menu_days"]
    dates = {d["label"]: d["date"] for d in days}
    assert dates == {"Idag": "2026-11-09", "Imorgon": "2026-11-10", "onsdag": "2026-11-11", "fredag": "2026-11-13"}
    assert [d["date"] for d in days] == sorted(d["date"] for d in days)


def test_no_menu_for_today_gives_no_state_before_15():
    food = {"Imorgon": ["B"], "onsdag": ["C"]}
    summary = summaries.summarize_menu(food, MORNING)
    assert summary["menu_state"] == "B"
    assert summary["menu_date"] == "2026-11-10"


def test_unknown_label_keeps_its_items_without_a_date():
    food = {"Veckans special": ["X"]}
    days = summaries.summarize_menu(food, MORNING)["menu_days"]
    assert days == [{"date": None, "label": "Veckans special", "items": ["X"]}]


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
