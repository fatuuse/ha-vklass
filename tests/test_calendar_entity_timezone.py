"""Check that calendar.py converts the requested window to local time before calling
get_calendar(), since Vklass expects local wall-clock times with a local offset.
Reads the source rather than running Home Assistant, since CalendarEntity needs it.
"""
from __future__ import annotations

import pathlib

CALENDAR_PY = (pathlib.Path(__file__).resolve().parents[1]
               / "custom_components" / "vklass" / "calendar.py").read_text()


def test_async_get_events_converts_to_local_time():
    assert "dt_util.as_local(start_date)" in CALENDAR_PY
    assert "dt_util.as_local(end_date)" in CALENDAR_PY


def test_dt_util_is_imported():
    assert "from homeassistant.util import dt as dt_util" in CALENDAR_PY


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
