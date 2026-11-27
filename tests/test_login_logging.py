"""Debug logging for login and session checks. Checks that the reason is logged and that
no credentials or cookie values appear in any log message. Invented data only."""
from __future__ import annotations

import importlib
import logging
import pathlib
import sys
import types
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_login_logging"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")
LOGGER = logging.getLogger(api.__name__)

SECRET_PASSWORD = "TEST-SECRET-PASSWORD"
SECRET_COOKIE = "TEST-SECRET-COOKIE"


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _capture():
    handler = Capture()
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.DEBUG)
    return handler


class RejectingSession:
    """Login page is fine, the sign-in POST answers 200, like a wrong password."""
    def __init__(self):
        self.cookies = SimpleNamespace(clear=lambda: None)

    def get(self, url, **kw):
        return SimpleNamespace(status_code=200, text='<input name="__RequestVerificationToken" type="hidden" value="TOKEN" />')

    def post(self, url, **kw):
        return SimpleNamespace(status_code=200, text="")


def test_rejected_login_logs_the_reason_without_the_password():
    handler = _capture()
    client = api.VklassClient("test-user", SECRET_PASSWORD)
    client._session = RejectingSession()
    try:
        client.login()
    except api.VklassAuthError:
        pass
    finally:
        LOGGER.removeHandler(handler)
    joined = "\n".join(handler.messages)
    assert "Login rejected" in joined
    assert SECRET_PASSWORD not in joined


def test_cookie_session_logs_that_no_sign_in_is_needed():
    handler = _capture()
    client = api.VklassClient(cookie=SECRET_COOKIE)
    try:
        client.ensure_login()
    finally:
        LOGGER.removeHandler(handler)
    joined = "\n".join(handler.messages)
    assert "no sign-in needed" in joined
    assert SECRET_COOKIE not in joined


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
