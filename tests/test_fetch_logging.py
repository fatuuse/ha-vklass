"""Debug logging for each page that is fetched. Invented data only."""
from __future__ import annotations

import importlib
import logging
import pathlib
import sys
import types
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_fetch_logging"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")
LOGGER = logging.getLogger(api.__name__)


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class FakeSession:
    def __init__(self, text: str):
        self.text = text
        self.cookies = []

    def request(self, method, url, **kw):
        return SimpleNamespace(status_code=200, text=self.text, json=lambda: {})


def test_path_masks_long_numbers_and_drops_the_query():
    assert api._path(f"{api.BASE_URL}/StudyOverview/Grades/1234567?school=9876") == "/StudyOverview/Grades/<id>"


def test_each_fetch_logs_the_page_without_ids_or_query():
    handler = Capture()
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.DEBUG)
    try:
        client = api.VklassClient("test-user", "test-pass")
        client._session = FakeSession("<html></html>")
        client.get_news()
    finally:
        LOGGER.removeHandler(handler)
    fetched = [m for m in handler.messages if m.startswith(("GET ", "POST ", "Fetched"))]
    assert fetched, handler.messages
    assert "/Home/News/" in fetched[0]
    assert "?" not in fetched[0]


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
