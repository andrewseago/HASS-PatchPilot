"""Runtime update manager."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.update import UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DRY_RUN,
    ATTR_ENTITY_ID,
    ATTR_IGNORE_WINDOW,
    CONF_CHECK_INTERVAL_MINUTES,
    CONF_CREATE_BACKUP,
    CONF_ENABLED,
    CONF_EXCLUDED_ENTITIES,
    CONF_EXCLUDE_PATTERNS,
    CONF_INCLUDE_PATTERNS,
    CONF_LOG_SIZE,
    CONF_MAX_UPDATES_PER_RUN,
    CONF_NOTIFY_ON_FAILURE,
    CONF_RUN_ON_STATE_CHANGE,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    DEFAULT_CHECK_INTERVAL_MINUTES,
    DEFAULT_CREATE_BACKUP,
    DEFAULT_ENABLED,
    DEFAULT_EXCLUDED_ENTITIES,
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_INCLUDE_PATTERNS,
    DEFAULT_LOG_SIZE,
    DEFAULT_MAX_UPDATES_PER_RUN,
    DEFAULT_NOTIFY_ON_FAILURE,
    DEFAULT_RUN_ON_STATE_CHANGE,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DOMAIN,
)
from .update_logic import UpdateCandidate, is_time_in_window, parse_time, select_pending_updates

_LOGGER = logging.getLogger(__name__)

UPDATE_DOMAIN = "update"
SERVICE_INSTALL = "install"
HOMEASSISTANT_DOMAIN = "homeassistant"
SERVICE_UPDATE_ENTITY = "update_entity"
PERSISTENT_NOTIFICATION_DOMAIN = "persistent_notification"
PERSISTENT_NOTIFICATION_CREATE = "create"


@dataclass(slots=True)
class UpdateRunResult:
    """Result from an update pass."""

    reason: str
    started_at: datetime
    finished_at: datetime | None = None
    dry_run: bool = False
    skipped_reason: str | None = None
    considered: list[str] = field(default_factory=list)
    installed: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


class PatchPilotManager:
    """Coordinate automatic Home Assistant update installs."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self._unsubs: list[Callable[[], None]] = []
        self._listeners: set[Callable[[], None]] = set()
        self._lock = asyncio.Lock()
        self.last_result: UpdateRunResult | None = None
        self.last_pending: list[str] = []
        self.history: list[dict[str, Any]] = []

    @property
    def options(self) -> dict[str, Any]:
        """Merged entry data and options."""
        return {**self.entry.data, **self.entry.options}

    @property
    def enabled(self) -> bool:
        """Return true when automatic updates are enabled."""
        return bool(self.options.get(CONF_ENABLED, DEFAULT_ENABLED))

    @property
    def check_interval_minutes(self) -> int:
        """Return polling interval in minutes."""
        return int(
            self.options.get(
                CONF_CHECK_INTERVAL_MINUTES, DEFAULT_CHECK_INTERVAL_MINUTES
            )
        )

    @property
    def include_patterns(self) -> list[str]:
        """Return include patterns."""
        value = self.options.get(CONF_INCLUDE_PATTERNS, DEFAULT_INCLUDE_PATTERNS)
        return _normalize_patterns(value)

    @property
    def exclude_patterns(self) -> list[str]:
        """Return exclude patterns."""
        value = self.options.get(CONF_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_PATTERNS)
        return _normalize_patterns(value)

    @property
    def excluded_entities(self) -> list[str]:
        """Return exact entity ids excluded from automatic updates."""
        value = self.options.get(CONF_EXCLUDED_ENTITIES, DEFAULT_EXCLUDED_ENTITIES)
        return _normalize_patterns(value)

    async def async_start(self) -> None:
        """Start scheduled checks and listeners."""
        interval = timedelta(minutes=self.check_interval_minutes)
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_interval, interval)
        )
        if self.options.get(CONF_RUN_ON_STATE_CHANGE, DEFAULT_RUN_ON_STATE_CHANGE):
            self._unsubs.append(
                self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._async_state_changed)
            )
        await self.async_scan()

    async def async_stop(self) -> None:
        """Stop scheduled checks and listeners."""
        while self._unsubs:
            self._unsubs.pop()()
        self._listeners.clear()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Add a state-change listener."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def _notify_listeners(self) -> None:
        """Notify attached entities."""
        for listener in tuple(self._listeners):
            listener()

    async def async_scan(self) -> None:
        """Refresh update entities and pending counters."""
        update_entities = [state.entity_id for state in self._update_states()]
        if update_entities:
            await self.hass.services.async_call(
                HOMEASSISTANT_DOMAIN,
                SERVICE_UPDATE_ENTITY,
                {},
                target={ATTR_ENTITY_ID: update_entities},
                blocking=True,
            )
        self.last_pending = [candidate.entity_id for candidate in self._pending_candidates()]
        self._notify_listeners()

    async def async_run(
        self,
        *,
        reason: str,
        entity_ids: Iterable[str] | None = None,
        ignore_window: bool = False,
        dry_run: bool = False,
    ) -> UpdateRunResult:
        """Run one update pass."""
        async with self._lock:
            result = UpdateRunResult(
                reason=reason,
                started_at=dt_util.utcnow(),
                dry_run=dry_run,
            )

            if not self.enabled and not ignore_window:
                result.skipped_reason = "disabled"
                return self._finish(result)

            if not ignore_window and not self._inside_window():
                result.skipped_reason = "outside_window"
                return self._finish(result)

            candidates = self._pending_candidates(entity_ids)
            result.considered = [candidate.entity_id for candidate in candidates]

            if dry_run:
                return self._finish(result)

            for candidate in candidates:
                try:
                    await self._async_install(candidate)
                except Exception as err:  # noqa: BLE001 - keep installing other entities.
                    _LOGGER.exception("Failed installing update for %s", candidate.entity_id)
                    result.failed[candidate.entity_id] = str(err)
                else:
                    result.installed.append(candidate.entity_id)

            if result.failed:
                self._create_failure_issue(result)
                await self._async_notify_failure(result)
            else:
                ir.async_delete_issue(self.hass, DOMAIN, self._failure_issue_id)

            await self.async_scan()
            return self._finish(result)

    async def _async_interval(self, _now: datetime) -> None:
        """Run periodic update pass."""
        await self.async_run(reason="interval")

    @callback
    def _async_state_changed(self, event: Event) -> None:
        """Run when a selected update entity becomes pending."""
        entity_id = event.data.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id.startswith(f"{UPDATE_DOMAIN}."):
            return
        new_state = event.data.get("new_state")
        if not isinstance(new_state, State) or new_state.state != "on":
            return
        self.hass.async_create_task(self.async_run(reason="state_changed"))

    def _finish(self, result: UpdateRunResult) -> UpdateRunResult:
        """Persist and notify a run result."""
        result.finished_at = dt_util.utcnow()
        self.last_result = result
        self._append_history(result)
        self.last_pending = [candidate.entity_id for candidate in self._pending_candidates()]
        self._notify_listeners()
        return result

    def _inside_window(self) -> bool:
        """Return true when current local time is in the maintenance window."""
        start = parse_time(str(self.options.get(CONF_WINDOW_START, DEFAULT_WINDOW_START)))
        end = parse_time(str(self.options.get(CONF_WINDOW_END, DEFAULT_WINDOW_END)))
        return is_time_in_window(dt_util.now().time(), start, end)

    def _update_states(self) -> list[State]:
        """Return all update entity states."""
        return [
            state
            for state in self.hass.states.async_all()
            if state.entity_id.startswith(f"{UPDATE_DOMAIN}.")
        ]

    def _pending_candidates(
        self, entity_ids: Iterable[str] | None = None
    ) -> list[UpdateCandidate]:
        """Return selected pending update candidates."""
        explicit_ids = set(entity_ids or [])
        candidates: list[UpdateCandidate] = []
        for state in self._update_states():
            if explicit_ids and state.entity_id not in explicit_ids:
                continue
            candidates.append(
                UpdateCandidate(
                    entity_id=state.entity_id,
                    state=state.state,
                    supported_features=int(state.attributes.get("supported_features", 0)),
                    attributes=state.attributes,
                )
            )
        return select_pending_updates(
            candidates,
            self.include_patterns,
            self.exclude_patterns,
            self.excluded_entities,
            int(UpdateEntityFeature.INSTALL),
            int(self.options.get(CONF_MAX_UPDATES_PER_RUN, DEFAULT_MAX_UPDATES_PER_RUN)),
        )

    async def async_set_entities_excluded(
        self, entity_ids: Iterable[str], excluded: bool
    ) -> None:
        """Persistently exclude or include update entities."""
        current = set(self.excluded_entities)
        if excluded:
            current.update(entity_ids)
        else:
            current.difference_update(entity_ids)

        options = {**self.entry.options}
        options[CONF_EXCLUDED_ENTITIES] = sorted(current)
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        await self.async_scan()
        self._notify_listeners()

    async def _async_install(self, candidate: UpdateCandidate) -> None:
        """Install one update entity."""
        service_data: dict[str, Any] = {}
        if self.options.get(CONF_CREATE_BACKUP, DEFAULT_CREATE_BACKUP) and (
            candidate.supported_features & int(UpdateEntityFeature.BACKUP)
        ):
            service_data["backup"] = True
        await self.hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            service_data,
            target={ATTR_ENTITY_ID: candidate.entity_id},
            blocking=True,
        )

    @property
    def _failure_issue_id(self) -> str:
        """Return repair issue id for this config entry."""
        return f"{self.entry.entry_id}_last_run_failed"

    def _create_failure_issue(self, result: UpdateRunResult) -> None:
        """Create or update a repair issue after failed installs."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._failure_issue_id,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="last_run_failed",
            translation_placeholders={
                "count": str(len(result.failed)),
                "entities": ", ".join(sorted(result.failed)),
            },
        )

    async def _async_notify_failure(self, result: UpdateRunResult) -> None:
        """Create a persistent notification after failed installs."""
        if not self.options.get(CONF_NOTIFY_ON_FAILURE, DEFAULT_NOTIFY_ON_FAILURE):
            return
        if not self.hass.services.has_service(
            PERSISTENT_NOTIFICATION_DOMAIN, PERSISTENT_NOTIFICATION_CREATE
        ):
            return
        entities = "\n".join(f"- `{entity_id}`: {error}" for entity_id, error in result.failed.items())
        await self.hass.services.async_call(
            PERSISTENT_NOTIFICATION_DOMAIN,
            PERSISTENT_NOTIFICATION_CREATE,
            {
                "title": "PatchPilot failed",
                "message": f"The last update run failed for:\n\n{entities}",
                "notification_id": f"{DOMAIN}_{self.entry.entry_id}_last_run_failed",
            },
            blocking=False,
        )

    def _append_history(self, result: UpdateRunResult) -> None:
        """Append one compact run-history entry."""
        entry = {
            "started_at": result.started_at.isoformat(),
            "finished_at": result.finished_at.isoformat() if result.finished_at else None,
            "reason": result.reason,
            "dry_run": result.dry_run,
            "skipped_reason": result.skipped_reason,
            "considered": result.considered,
            "installed": result.installed,
            "failed": result.failed,
        }
        self.history.insert(0, entry)
        max_size = int(self.options.get(CONF_LOG_SIZE, DEFAULT_LOG_SIZE))
        if max_size <= 0:
            self.history.clear()
        else:
            del self.history[max_size:]


def service_options_from_call(call_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize service-call options."""
    entity_ids = call_data.get(ATTR_ENTITY_ID)
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    return {
        "entity_ids": entity_ids,
        "ignore_window": bool(call_data.get(ATTR_IGNORE_WINDOW, False)),
        "dry_run": bool(call_data.get(ATTR_DRY_RUN, False)),
    }


def _normalize_patterns(value: Any) -> list[str]:
    """Normalize pattern input from config entries."""
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return [str(item).strip() for item in value if str(item).strip()]
