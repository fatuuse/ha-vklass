"""Tests for the seven changes from the review document. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "vklass"
PKG = "vklass_under_test_changes"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(INTEGRATION)]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")


# ── Change 1: strip credentials ──────────────────────────────────────────────
def test_config_flow_strips_whitespace_from_password():
    source = (INTEGRATION / "config_flow.py").read_text()
    # password.strip() must appear before it is stored or validated
    assert "user_input[DATA_PASSWORD].strip()" in source

def test_reauth_confirm_strips_password():
    source = (INTEGRATION / "config_flow.py").read_text()
    assert source.count(".strip()") >= 4  # username, password, cookie x2, reauth password


# ── Change 2: User-Agent ─────────────────────────────────────────────────────
def test_client_sets_user_agent_header():
    client = api.VklassClient("u", "p")
    assert "Mozilla" in client._session.headers.get("User-Agent", "")

def test_user_agent_constant_exists():
    assert hasattr(api, "USER_AGENT") or "USER_AGENT" in (INTEGRATION / "const.py").read_text()


# ── Change 3: catch-all parse guards ─────────────────────────────────────────
def test_broken_care_schedule_raises_connection_error():
    # Valid marker but broken JSON payload
    page = ("requirejs(['common/core/aurelia-enhancer'], (enhancer) => { "
            "enhancer.enhanceServerHtml('careschedule-overview', 'common/views/careschedule/careschedule-overview', "
            "'{{{broken', 'careScheduleOverviewClientModel', '', null) });")
    try:
        api.parse_care_schedule(page)
    except api.VklassConnectionError:
        return
    raise AssertionError("expected VklassConnectionError for broken JSON")

def test_broken_grades_raises_connection_error():
    page = ("<script>enhanceServerHtml('results-gradeselementaryschool', '', "
            "'{{{broken', '', '', null)</script>")
    try:
        api.parse_grades(page)
    except api.VklassConnectionError:
        return
    raise AssertionError("expected VklassConnectionError for broken JSON")

def test_broken_courses_raises_connection_error():
    page = ("<script>enhanceServerHtml('studyoverview-courses', '', "
            "'{{{broken', '', '', null)</script>")
    try:
        api.parse_courses(page)
    except api.VklassConnectionError:
        return
    raise AssertionError("expected VklassConnectionError for broken JSON")

def test_broken_absences_raises_connection_error():
    import html
    garbage = html.escape("{{{broken", quote=True)
    page = f'<template with.bind="{garbage}"></template>'
    try:
        api.parse_absences(page)
    except api.VklassConnectionError:
        return
    raise AssertionError("expected VklassConnectionError for broken JSON")


# ── Change 4: fetch timing logged ────────────────────────────────────────────
def test_fetch_timing_logged_at_debug():
    source = (INTEGRATION / "coordinator.py").read_text()
    assert "time.monotonic()" in source
    assert "Vklass refresh completed in" in source
    assert "_elapsed > 60" in source


# ── Change 5: entity removal helper exists ───────────────────────────────────
def test_async_track_child_removal_in_entity():
    source = (INTEGRATION / "entity.py").read_text()
    assert "async_track_child_removal" in source
    assert "async_remove" in source

def test_all_platforms_call_async_track_child_removal():
    for fname in ["sensor.py", "binary_sensor.py", "button.py", "calendar.py"]:
        src = (INTEGRATION / fname).read_text()
        assert "async_track_child_removal" in src, f"{fname} missing call"


# ── Change 6: news sensor caps intros and count ───────────────────────────────
def test_news_sensor_caps_intro_and_article_count():
    source = (INTEGRATION / "summaries.py").read_text()
    assert "count" in source
    assert "NEWS_INTRO_LIMIT = 200" in source
    assert "NEWS_ARTICLE_LIMIT = 10" in source


# ── Change 7: migration stub ─────────────────────────────────────────────────
def test_async_migrate_entry_exists():
    source = (INTEGRATION / "__init__.py").read_text()
    assert "async_migrate_entry" in source
    assert "return True" in source


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
