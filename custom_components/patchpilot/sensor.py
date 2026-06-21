"""Sensors for PatchPilot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
    """Set up PatchPilot sensors."""
    manager = hass.data[DOMAIN][DATA_MANAGERS][entry.entry_id]
    async_add_entities(
        [
            PendingUpdatesSensor(manager),
            InstallableUpdatesSensor(manager),
            SkippedUpdatesSensor(manager),
            LastRunSensor(manager),
            LastInstalledCountSensor(manager),
            LastFailedCountSensor(manager),
            RunHistorySensor(manager),
        ]
    )


class PatchPilotSensor(PatchPilotObservableEntity, SensorEntity):
    """Base sensor for PatchPilot."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: PatchPilotManager, key: str, name: str) -> None:
        """Initialize sensor."""
        super().__init__(manager, key, name)


class PendingUpdatesSensor(PatchPilotSensor):
    """Raw pending update count."""

    _attr_icon = "mdi:update"

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "pending_updates", "Pending updates")

    @property
    def native_value(self) -> int:
        """Return pending update count."""
        return len(self.manager.last_pending)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return pending entity ids and selection breakdown."""
        return {
            "entities": self.manager.last_pending,
            "installable_entities": self.manager.last_installable,
            "filtered_entities": self.manager.last_filtered,
            "uninstallable_entities": self.manager.last_uninstallable,
            "excluded_entities": self.manager.excluded_entities,
        }


class InstallableUpdatesSensor(PatchPilotSensor):
    """Installable pending update count."""

    _attr_icon = "mdi:package-up"

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "installable_updates", "Installable updates")

    @property
    def native_value(self) -> int:
        """Return installable pending update count."""
        return len(self.manager.last_installable)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return installable pending entity ids."""
        return {"entities": self.manager.last_installable}


class SkippedUpdatesSensor(PatchPilotSensor):
    """Skipped pending update count."""

    _attr_icon = "mdi:update-off"

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "skipped_updates", "Skipped updates")

    @property
    def native_value(self) -> int:
        """Return skipped pending update count."""
        return len(self.manager.last_filtered) + len(self.manager.last_uninstallable)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return skipped pending update entity ids."""
        return {
            "filtered_entities": self.manager.last_filtered,
            "uninstallable_entities": self.manager.last_uninstallable,
            "excluded_entities": self.manager.excluded_entities,
        }


class LastRunSensor(PatchPilotSensor):
    """Last update run timestamp."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, manager: PatchPilotManager) -> None:
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
            "filtered": result.filtered,
            "uninstallable": result.uninstallable,
            "skipped": result.filtered + result.uninstallable,
            "restart_required": result.restart_required,
            "scan_failed": result.scan_failed,
        }


class LastInstalledCountSensor(PatchPilotSensor):
    """Last installed update count."""

    _attr_icon = "mdi:package-up"

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "last_installed_count", "Last installed count")

    @property
    def native_value(self) -> int:
        """Return last installed count."""
        if self.manager.last_result is None:
            return 0
        return len(self.manager.last_result.installed)


class LastFailedCountSensor(PatchPilotSensor):
    """Last failed update count."""

    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize sensor."""
        super().__init__(manager, "last_failed_count", "Last failed count")

    @property
    def native_value(self) -> int:
        """Return last failure count."""
        if self.manager.last_result is None:
            return 0
        return len(self.manager.last_result.failed)


class RunHistorySensor(PatchPilotSensor):
    """Compact run-history sensor."""

    _attr_icon = "mdi:history"

    def __init__(self, manager: PatchPilotManager) -> None:
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
