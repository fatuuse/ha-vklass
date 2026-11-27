"""Embedded page data can contain JavaScript escapes such as \' that are not valid JSON.
The parsers must still read the data. Invented data only."""
from __future__ import annotations

import importlib
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = "vklass_under_test_js"
_pkg = types.ModuleType(PKG)
_pkg.__path__ = [str(ROOT / "custom_components" / "vklass")]
sys.modules[PKG] = _pkg

api = importlib.import_module(f"{PKG}.api")


def test_care_schedule_with_js_escaped_quote_is_read():
    # The instruction text uses \' inside the JS string, as the real page does.
    model_text = ('{"childInSchoolItems": [{"student": {"id": 111111}, "schoolId": 9001, "holidayData": {}}],'
                  '"schoolHolidayData": {"9001": [{"holidayId": 5001, "name": "Test", "startDate": "2026-12-21",'
                  '"endDate": "2027-01-08", "confirmationDeadlineDate": "2026-12-07",'
                  '"instructions": "Notera \\\'Ledig\\\'."}]},'
                  '"schoolClosedData": {}, "scheduleData": [{"studentId": 111111, "schoolId": 9001, '
                  '"date": "2026-11-16", "startTime": "07:45", "endTime": "16:15", "isOnLeave": false, "message": null}]}')
    page = ("requirejs(['x'], (e) => { e.enhanceServerHtml('careschedule-overview', 'common/views/careschedule/careschedule-overview', '"
            + model_text + "', 'careScheduleOverviewClientModel', '', null) });")
    children = api.parse_care_schedule(page)
    assert children[111111]["schedule"]["2026-11-16"]["start"] == "07:45"


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
