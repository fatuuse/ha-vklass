"""School id discovery must never sign in again. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_discovery"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")


class ForbiddenSession:
    """Every request is refused with 403, as Vklass does for the courses page without a school id."""

    def __init__(self):
        self.cookies = SimpleNamespace(clear=lambda: None)
        self.calls: list[str] = []

    def request(self, method, url, **kw):
        self.calls.append(url)
        return SimpleNamespace(status_code=403, text="")

    def get(self, url, **kw):
        self.calls.append(url)
        return SimpleNamespace(status_code=403, text="")

    def post(self, url, **kw):
        self.calls.append(url)
        return SimpleNamespace(status_code=403, text="")


def test_discovery_on_403_returns_empty_and_does_not_sign_in_again():
    session = ForbiddenSession()
    client = api.VklassClient("test-user", "test-pass")
    client._session = session
    assert client.discover_school_ids(111111) == []
    assert all(api.LOGIN_SIGNIN not in url and api.LOGIN_PAGE not in url for url in session.calls)


def _study_page(selected: str, others: list[str]) -> str:
    options = [f'<option class="" value="{selected}" selected="selected">Test school A</option>']
    options += [f'<option class="" value="{v}">Test school B</option>' for v in others]
    return ('<label>Skola</label><select id="SchoolId" class="mdc-select__native-control">'
            '<option value="">--- Välj ---</option>' + "".join(options) + "</select>")


def test_discovery_reads_the_school_selector_and_puts_the_selected_school_first():
    class Page:
        cookies = SimpleNamespace(clear=lambda: None)

        def request(self, method, url, **kw):
            return SimpleNamespace(status_code=200, text=_study_page("444444", ["555555"]))

    client = api.VklassClient("test-user", "test-pass")
    client._session = Page()
    assert client.discover_school_ids(111111) == [444444, 555555]


def test_no_school_selector_gives_an_empty_list():
    class Page:
        cookies = SimpleNamespace(clear=lambda: None)

        def request(self, method, url, **kw):
            return SimpleNamespace(status_code=200, text="<html>no selector</html>")

    client = api.VklassClient("test-user", "test-pass")
    client._session = Page()
    assert client.discover_school_ids(111111) == []


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
