"""Binary sensors for PatchPilot."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up PatchPilot binary sensors."""
    manager = hass.data[DOMAIN][DATA_MANAGERS][entry.entry_id]
    async_add_entities([RestartRequiredBinarySensor(manager)])


class RestartRequiredBinarySensor(PatchPilotObservableEntity, BinarySensorEntity):
    """Report when the last run needs a Home Assistant restart."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize binary sensor."""
        super().__init__(manager, "restart_required")

    @property
    def is_on(self) -> bool:
        """Return true when the last run requires a restart."""
        return bool(
            self.manager.last_result and self.manager.last_result.restart_required
        )
