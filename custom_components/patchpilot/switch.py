"""Switch entities for PatchPilot."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_MANAGERS, DOMAIN
from .entity import PatchPilotObservableEntity
from .manager import PatchPilotManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PatchPilot switches."""
    manager = hass.data[DOMAIN][DATA_MANAGERS][entry.entry_id]
    async_add_entities([PatchPilotSwitch(manager)])


class PatchPilotSwitch(PatchPilotObservableEntity, SwitchEntity):
    """Switch automatic PatchPilot update runs on or off."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:auto-fix"

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize switch."""
        super().__init__(manager, "automatic_updates", "Automatic updates")

    @property
    def is_on(self) -> bool:
        """Return true when automatic updates are enabled."""
        return self.manager.enabled

    async def async_turn_on(self, **_: object) -> None:
        """Enable automatic updates."""
        await self.manager.async_set_enabled(True)

    async def async_turn_off(self, **_: object) -> None:
        """Disable automatic updates."""
        await self.manager.async_set_enabled(False)
