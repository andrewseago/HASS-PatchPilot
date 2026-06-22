"""Repair flows for PatchPilot."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DATA_MANAGERS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PatchPilotFailedRunRepairFlow(RepairsFlow):
    """Offer to retry a failed PatchPilot update run or dismiss the issue."""

    def __init__(self, hass: HomeAssistant, entry_id: str | None) -> None:
        """Store the context needed to retry the failed run."""
        self.hass = hass
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Let the user choose to retry the failed updates or dismiss."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["retry", "dismiss"],
        )

    async def async_step_retry(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Re-run the updates that failed during the last run."""
        manager = self._manager()
        if manager is not None:
            try:
                await manager.async_retry_failed()
            except Exception:  # noqa: BLE001
                # Resolve the issue regardless; a fresh run reraises any failure.
                _LOGGER.exception("PatchPilot failed retrying the last update run")
        return self.async_create_entry(title="", data={})

    async def async_step_dismiss(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Dismiss the failed-run repair without retrying."""
        return self.async_create_entry(title="", data={})

    def _manager(self) -> Any | None:
        """Resolve the PatchPilot manager for this issue, if still loaded."""
        if self._entry_id is None:
            return None
        try:
            return self.hass.data[DOMAIN][DATA_MANAGERS][self._entry_id]
        except KeyError:
            return None


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for a PatchPilot repair issue."""
    entry_id = data.get("entry_id") if data else None
    return PatchPilotFailedRunRepairFlow(
        hass, entry_id if isinstance(entry_id, str) else None
    )
