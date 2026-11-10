"""Diagnostics for Vklass.

Credentials are redacted. Child names, student ids and school ids are never included,
so the file can be attached to an issue without exposing family information.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from .const import DATA_COOKIE, DATA_PASSWORD, DATA_USERNAME
from homeassistant.core import HomeAssistant

from . import VklassConfigEntry

TO_REDACT = {DATA_USERNAME, DATA_PASSWORD, DATA_COOKIE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VklassConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data or {}
    children = data.get("children", {})

    return {
        "config": async_redact_data(dict(entry.data), TO_REDACT),
        "school_ids_configured": len(entry.options.get("school_ids", {})),
        "children": [
            {
                "has_school_id": child.get("school_id") is not None,
                "fields_with_data": sorted(k for k, v in child.items() if v not in (None, [], {})),
            }
            for child in children.values()
        ],
        "news_items": len(data.get("news") or []),
        "scoreboard_keys": sorted((data.get("scoreboard") or {}).keys()),
    }
