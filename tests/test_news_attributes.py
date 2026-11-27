"""News sensor attributes: 10 newest articles, short intros, body only for the newest. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_news"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

summaries = importlib.import_module(f"{PKG}.summaries")


def _articles(n):
    return [{"id": i, "title": f"Test article {i}", "publish_date": f"2026-11-{i:02d}",
             "intro": "x" * 500, "text": f"Body {i} " + "y" * 6000, "url": f"https://example.invalid/{i}"}
            for i in range(1, n + 1)]


def test_ten_newest_articles_only():
    attrs = summaries.news_attributes(_articles(12))
    assert attrs["count"] == 12
    assert len(attrs["articles"]) == 10
    assert attrs["articles"][0]["publish_date"] == "2026-11-12"


def test_intros_are_capped_at_200_characters():
    for article in summaries.news_attributes(_articles(12))["articles"]:
        assert len(article["intro"]) <= 201  # 200 characters plus the ellipsis


def test_body_text_is_not_in_the_list_but_the_newest_body_is_in_latest_text():
    attrs = summaries.news_attributes(_articles(3))
    assert all("text" not in a for a in attrs["articles"])
    assert attrs["latest_text"].startswith("Body 3")
    assert len(attrs["latest_text"]) <= 4001


def test_no_articles_gives_empty_latest_text():
    attrs = summaries.news_attributes([])
    assert attrs == {"count": 0, "articles": [], "latest_text": ""}


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
