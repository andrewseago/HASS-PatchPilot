"""Sensors for PatchPilot."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_MANAGERS, DOMAIN
from .manager import AutoUpdateManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PatchPilot sensors."""
    manager = hass.data[DOMAIN][DATA_MANAGERS][entry.entry_id]
    async_add_entities(
        [
            PendingUpdatesSensor(manager),
            LastRunSensor(manager),
            LastInstalledCountSensor(manager),
            LastFailedCountSensor(manager),
            RunHistorySensor(manager),
        ]
    )


class AutoUpdateManagerSensor(SensorEntity):
    """Base sensor for PatchPilot."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: AutoUpdateManager, key: str, name: str) -> None:
        """Initialize sensor."""
        self.manager = manager
        self._attr_name = name
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._unsub: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to manager updates."""
        await super().async_added_to_hass()
        self._unsub = self.manager.async_add_listener(self._handle_manager_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from manager updates."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_manager_update(self) -> None:
        """Write sensor state after manager updates."""
        self.async_write_ha_state()


class PendingUpdatesSensor(AutoUpdateManagerSensor):
    """Pending update count."""

    _attr_icon = "mdi:update"

    def __init__(self, manager: AutoUpdateManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "pending_updates", "Pending updates")

    @property
    def native_value(self) -> int:
        """Return pending update count."""
        return len(self.manager.last_pending)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return pending entity ids."""
        return {
            "entities": self.manager.last_pending,
            "excluded_entities": self.manager.excluded_entities,
        }


class LastRunSensor(AutoUpdateManagerSensor):
    """Last update run timestamp."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, manager: AutoUpdateManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "last_run", "Last run")

    @property
    def native_value(self) -> datetime | None:
        """Return last run finish timestamp."""
        if self.manager.last_result is None:
            return None
        return self.manager.last_result.finished_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return last run details."""
        result = self.manager.last_result
        if result is None:
            return {}
        return {
            "reason": result.reason,
            "dry_run": result.dry_run,
            "skipped_reason": result.skipped_reason,
            "considered": result.considered,
            "installed": result.installed,
            "failed": result.failed,
        }


class LastInstalledCountSensor(AutoUpdateManagerSensor):
    """Last installed update count."""

    _attr_icon = "mdi:package-up"

    def __init__(self, manager: AutoUpdateManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "last_installed_count", "Last installed count")

    @property
    def native_value(self) -> int:
        """Return last installed count."""
        if self.manager.last_result is None:
            return 0
        return len(self.manager.last_result.installed)


class LastFailedCountSensor(AutoUpdateManagerSensor):
    """Last failed update count."""

    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager: AutoUpdateManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "last_failed_count", "Last failed count")

    @property
    def native_value(self) -> int:
        """Return last failure count."""
        if self.manager.last_result is None:
            return 0
        return len(self.manager.last_result.failed)


class RunHistorySensor(AutoUpdateManagerSensor):
    """Compact run-history sensor."""

    _attr_icon = "mdi:history"

    def __init__(self, manager: AutoUpdateManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "run_history", "Run history")

    @property
    def native_value(self) -> int:
        """Return retained run history count."""
        return len(self.manager.history)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return retained run history."""
        return {"runs": self.manager.history}
