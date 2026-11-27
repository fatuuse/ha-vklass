"""No children is an error, not an empty list. Idrott by title, day off, id from attributes, news fallback
and attachments. Invented data only."""
from __future__ import annotations

import html
import importlib
import json
import pathlib
import sys
import types
from datetime import date, timedelta
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_fetch"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")
summaries = importlib.import_module(f"{PKG}.summaries")


def _client(pages: dict[str, str]):
    client = api.VklassClient("test-user", "test-pass")
    client._request = lambda method, url, **kw: SimpleNamespace(
        text=pages.get(url, ""), status_code=200, json=lambda: [])
    return client


def test_welcome_page_without_children_raises_no_children_error():
    try:
        _client({api.HOME_URL: "<html>changed</html>"}).get_children()
    except api.VklassNoChildrenError as err:
        assert isinstance(err, api.VklassConnectionError)
        return
    raise AssertionError("expected VklassNoChildrenError")


def test_child_id_is_read_from_a_data_attribute_when_there_is_no_calendar_link():
    card = ('<div class="vk-student-card">'
            '<h2 class="vk-student-card-header__text">Test Child C</h2>'
            '<div data-student-id="333333"></div></div>\r\n\t\t\t\t\t\r\n\r\n')
    children = _client({api.HOME_URL: card}).get_children()
    assert children["333333"]["name"] == "Test Child C"


def test_gym_is_recognised_by_title_as_well_as_code():
    assert summaries.is_idrott({"title": "Idrott och hälsa", "code": ""}) is True
    assert summaries.is_idrott({"title": "Test lesson", "code": "IDH"}) is True
    assert summaries.is_idrott({"title": "Gympa utomhus", "code": ""}) is True
    assert summaries.is_idrott({"title": "Matematik", "code": "MA"}) is False


def test_calendar_event_type_8_is_a_day_off():
    payload = [{"title": "Test day off", "start": "2026-11-09 00:00", "end": None, "eventType": 8,
                "className": "", "cancelled": False, "allDay": True}]
    client = api.VklassClient("test-user", "test-pass")
    client._request = lambda method, url, **kw: SimpleNamespace(json=lambda: payload, text="", status_code=200)
    assert client.get_calendar(111111)[0]["category"] == "vacantday"


def test_news_falls_back_to_the_welcome_page_when_the_news_data_is_missing():
    today = date.today()
    article = {"id": 4444, "title": "Test news", "publishDate": (today - timedelta(days=1)).isoformat(),
               "introText": "Intro", "text": "Body", "tags": [], "files": [], "children": []}
    escaped = html.escape(json.dumps(article), quote=True)
    welcome = f'<div><vkau-news-article article.bind="{escaped}" teaser-mode.bind="true"></vkau-news-article></div>'
    pages = {api.NEWS_URL: "<html>no data here</html>", api.HOME_URL: welcome}
    news = _client(pages).get_news()
    assert [a["title"] for a in news] == ["Test news"]
    assert news[0]["url"].endswith("/Home/News/4444")


def test_news_attachments_are_kept_as_absolute_links():
    today = date.today()
    article = {"id": 5555, "title": "Test news with file", "publishDate": (today - timedelta(days=1)).isoformat(),
               "introText": "", "text": "", "tags": [], "children": [],
               "files": [{"nameWithExtension": "Test letter.pdf", "url": "https://files.example.invalid/letter.pdf"},
                         {"name": "Relative", "url": "/Files/relative.pdf"}]}
    data = {"newsArticles": [article]}
    page = ("<script>enhanceServerHtml('x', 'common/views/shared/display-templates/news-feed-model/news-feed-model', '"
            + json.dumps(data) + "', '', '', null)</script>")
    news = _client({api.NEWS_URL: page}).get_news()
    files = news[0]["files"]
    assert files[0] == {"name": "Test letter.pdf", "url": "https://files.example.invalid/letter.pdf"}
    assert files[1]["url"].startswith("https://custodian.vklass.se/")


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
