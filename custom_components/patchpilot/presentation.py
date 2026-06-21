"""Pure notification text builders for PatchPilot.

Stdlib only: no Home Assistant imports, so this module is unit-testable by
direct import. The manager resolves entity friendly names and delegates all
persistent-notification title/message text to these functions.
"""

from __future__ import annotations

from collections.abc import Iterable


def format_entity(entity_id: str, names: dict[str, str]) -> str:
    """Format one entity as 'Friendly Name (`entity_id`)', or '`entity_id`'.

    Falls back to the bare quoted entity id when no friendly name is known.
    """
    name = names.get(entity_id)
    if name:
        return f"{name} (`{entity_id}`)"
    return f"`{entity_id}`"


def _format_entity_list(entity_ids: Iterable[str], names: dict[str, str]) -> str:
    """Format a bulleted list of entities, one per line."""
    return "\n".join(f"- {format_entity(entity_id, names)}" for entity_id in entity_ids)


def format_skipped_sections(
    filtered: list[str], uninstallable: list[str], names: dict[str, str]
) -> str:
    """Format skipped pending updates into two labeled sections.

    Returns an empty string when nothing was skipped.
    """
    sections: list[str] = []
    if filtered:
        sections.append(
            "Filtered by PatchPilot configuration:\n"
            f"{_format_entity_list(filtered, names)}"
        )
    if uninstallable:
        sections.append(
            "Pending but not installable through Home Assistant:\n"
            f"{_format_entity_list(uninstallable, names)}"
        )
    return "\n\n".join(sections)


def build_failure_notification(
    failed: dict[str, str], names: dict[str, str]
) -> tuple[str, str]:
    """Build the (title, message) for failed update installs."""
    entities = "\n".join(
        f"- {format_entity(entity_id, names)}: {error}"
        for entity_id, error in failed.items()
    )
    message = f"The last update run failed for:\n\n{entities}"
    return "PatchPilot failed", message


def _skipped_tail(
    filtered: list[str], uninstallable: list[str], names: dict[str, str]
) -> str:
    """Optional trailing block listing skipped pending updates."""
    skipped = format_skipped_sections(filtered, uninstallable, names)
    if not skipped:
        return ""
    return "\n\nPatchPilot did not install these pending updates:\n\n" + skipped


def build_restart_required_notification(
    installed: list[str],
    restart_required: list[str],
    filtered: list[str],
    uninstallable: list[str],
    names: dict[str, str],
) -> tuple[str, str]:
    """Build the (title, message) requesting a Home Assistant restart."""
    installed_list = _format_entity_list(installed, names)
    restart_list = _format_entity_list(restart_required, names)
    message = (
        "PatchPilot finished installing updates for:\n\n"
        f"{installed_list}\n\n"
        "Restart Home Assistant to finish applying these updates:\n\n"
        f"{restart_list}"
        f"{_skipped_tail(filtered, uninstallable, names)}"
    )
    return "PatchPilot restart required", message


def build_updates_installed_notification(
    installed: list[str],
    filtered: list[str],
    uninstallable: list[str],
    names: dict[str, str],
) -> tuple[str, str]:
    """Build the (title, message) for installs needing no HA restart."""
    installed_list = _format_entity_list(installed, names)
    message = (
        "PatchPilot finished installing updates for:\n\n"
        f"{installed_list}\n\n"
        "PatchPilot did not detect a Home Assistant restart requirement "
        "for these update entities."
        f"{_skipped_tail(filtered, uninstallable, names)}"
    )
    return "PatchPilot updates installed", message


def build_skipped_updates_notification(
    filtered: list[str], uninstallable: list[str], names: dict[str, str]
) -> tuple[str, str]:
    """Build the (title, message) listing skipped pending updates."""
    sections = format_skipped_sections(filtered, uninstallable, names)
    message = f"PatchPilot will not install these pending updates:\n\n{sections}"
    return "PatchPilot skipped updates", message
