"""Regression tests for bugs found in real use. Invented data only."""
from __future__ import annotations

import importlib
import json
import pathlib
import sys
import types
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "vklass"
PKG = "vklass_under_test_regressions"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(INTEGRATION)]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")


def test_discovered_is_initialised_in_the_coordinator_constructor():
    """The coordinator must set _discovered in __init__, not somewhere it only runs later."""
    source = (INTEGRATION / "coordinator.py").read_text()
    init_body = source[source.index("    def __init__(self, hass"):source.index("    def _on_cookie_update")]
    assert "self._discovered" in init_body


def test_password_login_starts_from_an_empty_cookie_jar():
    cleared = []

    class Session:
        cookies = SimpleNamespace(clear=lambda: cleared.append(True))

        def get(self, *a, **k):
            raise api.VklassConnectionError("stop after the cookie check")

    client = api.VklassClient("test-user", "test-pass")
    client._session = Session()
    try:
        client.login()
    except api.VklassConnectionError:
        pass
    assert cleared == [True]


def test_every_user_visible_label_exists_in_both_languages():
    for path in ["translations/en.json", "translations/sv.json"]:
        data = json.loads((INTEGRATION / path).read_text())
        assert data["config"]["step"]["user"]["data"]["auth_method"]
        for section in (data["config"]["step"]["settings"]["data"], data["options"]["step"]["init"]["data"]):
            assert section["calendar_categories"]
            assert section["hide_multiday_all_day"]


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
