"""Offline tests for keepalive and cookie rotation. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_keepalive"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")


class FakeSession:
    def __init__(self, text: str, json_value=None, cookie_value: str | None = None):
        self.text = text
        self.json_value = json_value
        self.calls: list[dict] = []
        self.cookies = []
        if cookie_value is not None:
            self.cookies = [SimpleNamespace(name=api.COOKIE_NAME, value=cookie_value)]

    def request(self, method, url, **kw):
        self.calls.append({"method": method, "url": url, **kw})
        if self.json_value is None:
            def fail():
                raise ValueError("not json")
            return SimpleNamespace(status_code=200, text=self.text, json=fail)
        return SimpleNamespace(status_code=200, text=self.text, json=lambda: self.json_value)


def test_ping_hits_scoreboard_with_timestamp():
    session = FakeSession("{}", json_value={"notifications": 0, "messages": 0})
    client = api.VklassClient(cookie="TEST-COOKIE")
    client._session = session
    client.ping()
    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == api.SCOREBOARD_URL
    assert isinstance(call["params"]["_"], int)
    assert call["params"]["_"] > 1_700_000_000_000  # milliseconds since the epoch


def test_non_json_response_means_the_session_expired():
    client = api.VklassClient(cookie="TEST-COOKIE")
    client._session = FakeSession("<html>login</html>")
    try:
        client.ping()
    except api.VklassAuthError:
        return
    raise AssertionError("expected VklassAuthError when the scoreboard returns HTML")


def test_rotated_cookie_is_reported_to_the_owner():
    updates: list[str] = []
    client = api.VklassClient(cookie="OLD-COOKIE", on_cookie_update=updates.append)
    client._session = FakeSession("{}", json_value={"notifications": 0, "messages": 0},
                                  cookie_value="NEW-COOKIE")
    client.ping()
    assert updates == ["NEW-COOKIE"]
    assert client._cookie == "NEW-COOKIE"


def test_unchanged_cookie_is_not_reported():
    updates: list[str] = []
    client = api.VklassClient(cookie="SAME-COOKIE", on_cookie_update=updates.append)
    client._session = FakeSession("{}", json_value={"notifications": 0, "messages": 0},
                                  cookie_value="SAME-COOKIE")
    client.ping()
    assert updates == []


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
