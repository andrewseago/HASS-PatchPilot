"""Pure update-selection helpers for PatchPilot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from fnmatch import fnmatchcase
from typing import Iterable, Mapping

STATE_PENDING = "on"


@dataclass(frozen=True)
class UpdateCandidate:
    """Normalized update entity state used by the manager."""

    entity_id: str
    state: str
    supported_features: int = 0
    attributes: Mapping[str, object] | None = None


@dataclass(frozen=True)
class UpdateSelectionSummary:
    """Breakdown of pending update entities."""

    pending: list[UpdateCandidate]
    installable: list[UpdateCandidate]
    uninstallable: list[UpdateCandidate]
    filtered: list[UpdateCandidate]


def parse_time(value: str) -> time:
    """Parse a Home Assistant-style time string."""
    parts = value.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError("time must be HH:MM or HH:MM:SS")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    return time(hour, minute, second)


def is_time_in_window(now: time, start: time, end: time) -> bool:
    """Return true when now is inside the configured maintenance window."""
    if start == end:
        return True
    if start < end:
        return start <= now < end
    return now >= start or now < end


def matches_any(entity_id: str, patterns: Iterable[str]) -> bool:
    """Return true when an entity id matches any shell-style pattern."""
    return any(fnmatchcase(entity_id, pattern) for pattern in patterns)


def is_allowed_entity(
    entity_id: str,
    include_patterns: Iterable[str],
    exclude_patterns: Iterable[str],
    excluded_entities: Iterable[str] = (),
) -> bool:
    """Return true when an entity id is selected by include/exclude patterns."""
    if entity_id in set(excluded_entities):
        return False
    return matches_any(entity_id, include_patterns) and not matches_any(
        entity_id, exclude_patterns
    )


def select_pending_updates(
    candidates: Iterable[UpdateCandidate],
    include_patterns: Iterable[str],
    exclude_patterns: Iterable[str],
    excluded_entities: Iterable[str],
    install_feature: int,
    max_updates: int = 0,
) -> list[UpdateCandidate]:
    """Select pending installable update entities."""
    return summarize_update_candidates(
        candidates,
        include_patterns,
        exclude_patterns,
        excluded_entities,
        install_feature,
        max_updates,
    ).installable


def summarize_update_candidates(
    candidates: Iterable[UpdateCandidate],
    include_patterns: Iterable[str],
    exclude_patterns: Iterable[str],
    excluded_entities: Iterable[str],
    install_feature: int,
    max_updates: int = 0,
) -> UpdateSelectionSummary:
    """Return a breakdown of pending update entities and selected installs."""
    pending: list[UpdateCandidate] = []
    installable: list[UpdateCandidate] = []
    uninstallable: list[UpdateCandidate] = []
    filtered: list[UpdateCandidate] = []

    for candidate in candidates:
        if candidate.state != STATE_PENDING:
            continue

        pending.append(candidate)
        if not is_allowed_entity(
            candidate.entity_id,
            include_patterns,
            exclude_patterns,
            excluded_entities,
        ):
            filtered.append(candidate)
            continue

        if not candidate.supported_features & install_feature:
            uninstallable.append(candidate)
            continue

        if max_updates <= 0 or len(installable) < max_updates:
            installable.append(candidate)

    return UpdateSelectionSummary(
        pending=pending,
        installable=installable,
        uninstallable=uninstallable,
        filtered=filtered,
    )
