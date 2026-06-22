"""Shared PatchPilot entity helpers."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .manager import PatchPilotManager


class PatchPilotEntity:
    """Base entity metadata for PatchPilot."""

    _attr_has_entity_name = True

    def __init__(self, manager: PatchPilotManager, key: str) -> None:
        """Initialize entity metadata."""
        self.manager = manager
        self._attr_translation_key = key
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the PatchPilot device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.manager.entry.entry_id)},
            name=self.manager.entry.title or "PatchPilot",
            manufacturer="PatchPilot",
            model="Update automation manager",
            configuration_url=f"homeassistant://config/integrations/integration/{DOMAIN}",
        )


class PatchPilotObservableEntity(PatchPilotEntity):
    """Entity that updates when the manager state changes."""

    def __init__(self, manager: PatchPilotManager, key: str) -> None:
        """Initialize observable entity metadata."""
        super().__init__(manager, key)
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
        """Write entity state after manager updates."""
        self.async_write_ha_state()
