"""Every translation_key used in code must have a name in every language file."""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "vklass"
LANGUAGES = ["en", "sv"]


def _keys_in_code() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for module, platform in [("sensor.py", "sensor"), ("binary_sensor.py", "binary_sensor")]:
        text = (INTEGRATION / module).read_text()
        found[platform] = set(re.findall(r'translation_key="(\w+)"', text))
    found["calendar"] = set(re.findall(r'_attr_translation_key = "(\w+)"',
                                       (INTEGRATION / "calendar.py").read_text()))
    found["button"] = set(re.findall(r'_attr_translation_key = "(\w+)"',
                                     (INTEGRATION / "button.py").read_text()))
    return found


def test_every_entity_key_has_a_name_in_every_language():
    keys = _keys_in_code()
    for lang in LANGUAGES:
        data = json.loads((INTEGRATION / "translations" / f"{lang}.json").read_text())
        for platform, used in keys.items():
            defined = set(data["entity"][platform])
            missing = used - defined
            assert not missing, f"{lang}: missing {platform} names for {sorted(missing)}"


# Names that are the same word in both languages. These are allowed on purpose.
SAME_IN_BOTH = {("sensor", "menu")}


def test_swedish_names_are_not_english_copies():
    base = INTEGRATION / "translations"
    sv = json.loads((base / "sv.json").read_text())["entity"]
    en = json.loads((base / "en.json").read_text())["entity"]
    same = {
        (platform, key)
        for platform in sv
        for key in sv[platform]
        if sv[platform][key] == en[platform][key] and (platform, key) not in SAME_IN_BOTH
    }
    assert not same, f"Swedish names identical to English for {sorted(same)}"


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} tests passed")
