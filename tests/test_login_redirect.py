"""The sign-in redirect is followed, and a second sign-in right after success is not started."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_redirect"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")


class SignInSession:
    def __init__(self):
        self.cookies = SimpleNamespace(clear=lambda: None)
        self.gets: list[str] = []

    def get(self, url, **kw):
        self.gets.append(url)
        if "signin" in url or url == api.LOGIN_PAGE:
            return SimpleNamespace(status_code=200, text='<input name="__RequestVerificationToken" type="hidden" value="T" />')
        return SimpleNamespace(status_code=200, text="")

    def post(self, url, **kw):
        return SimpleNamespace(status_code=302, text="", headers={"Location": "/Home/Welcome"})


def test_sign_in_redirect_is_followed():
    session = SignInSession()
    client = api.VklassClient("test-user", "test-pass")
    client._session = session
    client.login()
    assert any(u.endswith("/Home/Welcome") for u in session.gets)


def test_no_second_sign_in_right_after_success():
    client = api.VklassClient("test-user", "test-pass")
    client._session = SignInSession()
    client.login()

    class Redirecting:
        def request(self, *a, **k):
            return SimpleNamespace(status_code=302, text="", headers={})

    client._session = Redirecting()
    try:
        client.get_children()
    except api.VklassConnectionError:
        return
    raise AssertionError("expected VklassConnectionError, not a second sign-in")


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
