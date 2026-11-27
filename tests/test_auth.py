"""Offline tests for cookie and password sessions. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_auth"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")


class NoNetwork:
    def request(self, *a, **k):
        raise AssertionError("network used")

    get = post = request


class Redirecting:
    """Every request is redirected to the login page, as an expired session would be."""

    def request(self, method, url, **kw):
        return SimpleNamespace(status_code=302, text="")


def test_cookie_is_stored_for_the_vklass_domain():
    client = api.VklassClient(cookie="TEST-COOKIE")
    assert client._session.cookies.get(api.COOKIE_NAME, domain=api.COOKIE_DOMAIN) == "TEST-COOKIE"


def test_cookie_session_never_logs_in_over_the_network():
    client = api.VklassClient(cookie="TEST-COOKIE")
    client._session = NoNetwork()
    client.ensure_login()
    client.login()


def test_expired_cookie_raises_auth_error_not_connection_error():
    client = api.VklassClient(cookie="TEST-COOKIE")
    client._session = Redirecting()
    try:
        client.get_children()
    except api.VklassAuthError:
        return
    raise AssertionError("expected VklassAuthError for an expired cookie")


def test_client_for_data_picks_the_right_login():
    cookie_client = api.client_for_data({"auth_method": "cookie", "cookie": "TEST-COOKIE"})
    assert cookie_client._cookie == "TEST-COOKIE"
    password_client = api.client_for_data({"username": "test-user", "password": "test-pass"})
    assert password_client._username == "test-user"
    assert password_client._cookie is None


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
