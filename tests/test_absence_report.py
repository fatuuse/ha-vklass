"""Offline tests for reporting an absence for today. Invented data only."""
from __future__ import annotations

import html
import importlib
import json
import pathlib
import sys
import types
from datetime import datetime
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_absence"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")

CHILD_A = 111111
NOW = datetime(2026, 11, 9, 10, 0)


def _form(absences, minimum="2026-11-09 08:00:00", maximum="2026-11-11 20:00:00") -> str:
    template = html.escape(json.dumps({"absences": absences}), quote=True)
    return ('<input name="__RequestVerificationToken" type="hidden" value="TEST-TOKEN" />'
            f'<input type="hidden" id="Notify_MinimumStartDateTime" name="Notify.MinimumStartDateTime" value="{minimum}" />'
            f'<input type="hidden" id="Notify_MaximumEndDateTime" name="Notify.MaximumEndDateTime" value="{maximum}" />'
            f'<template with.bind="{template}"></template>')


def _report(start: str, end: str) -> dict:
    return {"id": 9, "studentId": CHILD_A, "absenceType": "VALID", "createdBy": "Test Teacher",
            "startDateTime": start, "endDateTime": end}


class Fake:
    def __init__(self, gets):
        self.gets = list(gets)
        self.posts = []

    def __call__(self, method, url, **kw):
        if method == "POST":
            self.posts.append(kw.get("data", {}))
            return SimpleNamespace(text="", status_code=200)
        return SimpleNamespace(text=self.gets.pop(0), status_code=200)


def _client(fake: Fake):
    client = api.VklassClient("user", "pass")
    client._request = fake
    return client


def test_reports_absence_and_verifies_it():
    fake = Fake([_form([]), _form([_report("2026-11-09 10:00", "2026-11-09 23:59")])])
    assert _client(fake).report_absence_today(CHILD_A, NOW) == "reported"
    data = fake.posts[0]
    assert data["__RequestVerificationToken"] == "TEST-TOKEN"
    assert data["Notify.SelectedStudentIds"] == str(CHILD_A)
    assert data["Notify.StartDate"] == "2026-11-09"
    assert data["Notify.StartTime"] == "10:00"
    assert data["Notify.EndTime"] == "23:59"
    assert data["Notify.QuickOptionDateIsNull"] == "True"


def test_does_not_report_twice():
    fake = Fake([_form([_report("2026-11-09 07:00", "2026-11-09 23:59")])])
    assert _client(fake).report_absence_today(CHILD_A, NOW) == "already_absent"
    assert fake.posts == []


def test_fails_when_vklass_does_not_confirm():
    fake = Fake([_form([]), _form([])])
    try:
        _client(fake).report_absence_today(CHILD_A, NOW)
    except api.VklassConnectionError:
        return
    raise AssertionError("expected VklassConnectionError when the report is not confirmed")


def test_fails_when_the_window_for_today_is_closed():
    fake = Fake([_form([], minimum="2026-11-10 08:00:00")])
    try:
        _client(fake).report_absence_today(CHILD_A, NOW)
    except api.VklassConnectionError:
        assert fake.posts == []
        return
    raise AssertionError("expected VklassConnectionError when today's window is closed")


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
