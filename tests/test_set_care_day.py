"""The set_care_day client call posts the same form as the care schedule page, and raises on failure.
Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from datetime import date
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_set_care"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")

PAGE = '<form><input name="__RequestVerificationToken" type="hidden" value="TEST-TOKEN" /></form>'


def _client(post_json):
    client = api.VklassClient("test-user", "test-pass")
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET":
            return SimpleNamespace(text=PAGE, status_code=200)
        return SimpleNamespace(status_code=200, text="", json=lambda: post_json)

    client._request = fake_request
    client.ensure_login = lambda: None
    return client, calls


def test_set_care_day_posts_the_form_fields_and_token():
    success = {"alert": {"contextCssClass": "success", "message": "Saved."}}
    client, calls = _client(success)
    client.set_care_day(111111, 9001, date(2026, 11, 16), "08:00", "16:00", False, "Test message.")
    method, url, kwargs = calls[-1]
    assert method == "POST" and url.endswith("/CareSchedule/SaveChanges")
    data = kwargs["data"]
    assert data["Changes[0].StudentId"] == "111111"
    assert data["Changes[0].Date"] == "2026-11-16"
    assert data["Changes[0].StartTime"] == "08:00"
    assert data["__RequestVerificationToken"] == "TEST-TOKEN"


def test_failed_save_raises_with_vklass_message():
    failure = {"alert": {"contextCssClass": "danger", "message": "Test refusal."}}
    client, _ = _client(failure)
    try:
        client.set_care_day(111111, 9001, date(2026, 11, 16), "08:00", "16:00", False, "")
    except api.VklassConnectionError as err:
        assert "Test refusal." in str(err)
        return
    raise AssertionError("expected VklassConnectionError")


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
