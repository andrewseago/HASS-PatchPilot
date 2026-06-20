"""Button entities for PatchPilot."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_MANAGERS, DOMAIN
from .entity import PatchPilotEntity
from .manager import PatchPilotManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PatchPilot buttons."""
    manager = hass.data[DOMAIN][DATA_MANAGERS][entry.entry_id]
    async_add_entities(
        [
            ScanUpdatesButton(manager),
            DryRunButton(manager),
            RunUpdatesButton(manager),
        ]
    )


class PatchPilotButton(PatchPilotEntity, ButtonEntity):
    """Base PatchPilot button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, manager: PatchPilotManager, key: str, name: str, icon: str
    ) -> None:
        """Initialize button."""
        super().__init__(manager, key, name)
        self._attr_icon = icon


class ScanUpdatesButton(PatchPilotButton):
    """Refresh update status."""

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize button."""
        super().__init__(manager, "scan_updates", "Scan updates", "mdi:refresh")

    async def async_press(self) -> None:
        """Refresh update entities and PatchPilot counters."""
        await self.manager.async_scan()


class DryRunButton(PatchPilotButton):
    """Preview selected updates."""

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize button."""
        super().__init__(manager, "dry_run", "Dry run", "mdi:clipboard-search")

    async def async_press(self) -> None:
        """Run update selection without installing anything."""
        await self.manager.async_run(
            reason="button_dry_run",
            ignore_window=True,
            dry_run=True,
        )


class RunUpdatesButton(PatchPilotButton):
    """Run selected updates now."""

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize button."""
        super().__init__(manager, "run_updates_now", "Run updates now", "mdi:play")

    async def async_press(self) -> None:
        """Install selected pending update entities now."""
        await self.manager.async_run(reason="button", ignore_window=True)
