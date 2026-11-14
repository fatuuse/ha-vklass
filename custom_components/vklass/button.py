"""Button platform: report an absence for today, one button per child.

The button is disabled by default in the entity registry. Enable it deliberately,
because pressing it reports an absence to the school.
"""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VklassConfigEntry
from .api import VklassAuthError, VklassConnectionError
from .coordinator import VklassCoordinator
from .entity import VklassChildEntity, async_track_child_removal


class VklassReportAbsenceButton(VklassChildEntity, ButtonEntity):
    _attr_icon = "mdi:account-off-outline"
    _attr_translation_key = "report_absence"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: VklassCoordinator, entry: VklassConfigEntry, child_key: str) -> None:
        super().__init__(coordinator, entry, child_key, "report_absence")

    async def async_press(self) -> None:
        try:
            result = await self.hass.async_add_executor_job(
                self.coordinator.client.report_absence_today,
                self.child["id"],
                datetime.now(),
            )
        except VklassAuthError as err:
            raise HomeAssistantError("Vklass rejected the login. Re-authenticate the integration.") from err
        except VklassConnectionError as err:
            raise HomeAssistantError(f"Could not report absence: {err}") from err

        if result == "already_absent":
            raise HomeAssistantError("An absence is already reported for this child right now.")
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VklassConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities_by_child: dict[str, list] = {
        key: [VklassReportAbsenceButton(coordinator, entry, key)]
        for key, child in coordinator.data["children"].items()
        if child["id"] is not None
    }
    async_add_entities(e for elist in entities_by_child.values() for e in elist)
    async_track_child_removal(coordinator, entry, entities_by_child)
