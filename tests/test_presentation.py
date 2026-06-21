"""Tests for PatchPilot pure notification presentation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "patchpilot"
    / "presentation.py"
)
SPEC = importlib.util.spec_from_file_location("patchpilot_presentation", MODULE_PATH)
assert SPEC is not None
presentation = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = presentation
SPEC.loader.exec_module(presentation)

format_entity = presentation.format_entity
format_skipped_sections = presentation.format_skipped_sections
build_failure_notification = presentation.build_failure_notification
build_restart_required_notification = presentation.build_restart_required_notification
build_updates_installed_notification = presentation.build_updates_installed_notification
build_skipped_updates_notification = presentation.build_skipped_updates_notification


class FormatEntityTests(unittest.TestCase):
    """Test single-entity formatting."""

    def test_uses_friendly_name_with_id_when_known(self) -> None:
        names = {"update.home_assistant_core_update": "Home Assistant Core"}
        self.assertEqual(
            format_entity("update.home_assistant_core_update", names),
            "Home Assistant Core (`update.home_assistant_core_update`)",
        )

    def test_falls_back_to_bare_id_when_name_missing(self) -> None:
        self.assertEqual(format_entity("update.foo", {}), "`update.foo`")
        self.assertEqual(
            format_entity("update.foo", {"update.bar": "Bar"}),
            "`update.foo`",
        )


class FormatSkippedSectionsTests(unittest.TestCase):
    """Test the two labeled skipped sections."""

    def test_empty_when_no_skipped(self) -> None:
        self.assertEqual(format_skipped_sections([], [], {}), "")

    def test_filtered_only_section(self) -> None:
        names = {"update.router": "Router"}
        self.assertEqual(
            format_skipped_sections(["update.router"], [], names),
            "Filtered by PatchPilot configuration:\n- Router (`update.router`)",
        )

    def test_uninstallable_only_section(self) -> None:
        self.assertEqual(
            format_skipped_sections([], ["update.hacs"], {}),
            "Pending but not installable through Home Assistant:\n- `update.hacs`",
        )

    def test_both_sections_joined_by_blank_line(self) -> None:
        result = format_skipped_sections(
            ["update.router"], ["update.hacs"], {"update.router": "Router"}
        )
        self.assertEqual(
            result,
            "Filtered by PatchPilot configuration:\n"
            "- Router (`update.router`)\n\n"
            "Pending but not installable through Home Assistant:\n"
            "- `update.hacs`",
        )


class BuildFailureNotificationTests(unittest.TestCase):
    """Test the failure notification."""

    def test_title_and_body(self) -> None:
        title, message = build_failure_notification(
            {"update.core": "boom", "update.os": "nope"},
            {"update.core": "HA Core"},
        )
        self.assertEqual(title, "PatchPilot failed")
        self.assertEqual(
            message,
            "The last update run failed for:\n\n"
            "- HA Core (`update.core`): boom\n"
            "- `update.os`: nope",
        )


class BuildRestartRequiredNotificationTests(unittest.TestCase):
    """Test the restart-required notification."""

    def test_without_skipped_tail(self) -> None:
        title, message = build_restart_required_notification(
            ["update.core", "update.hacs"],
            ["update.core"],
            [],
            [],
            {"update.core": "HA Core"},
        )
        self.assertEqual(title, "PatchPilot restart required")
        self.assertEqual(
            message,
            "PatchPilot finished installing updates for:\n\n"
            "- HA Core (`update.core`)\n"
            "- `update.hacs`\n\n"
            "Restart Home Assistant to finish applying these updates:\n\n"
            "- HA Core (`update.core`)",
        )

    def test_with_skipped_tail(self) -> None:
        _title, message = build_restart_required_notification(
            ["update.core"],
            ["update.core"],
            ["update.router"],
            [],
            {},
        )
        self.assertEqual(
            message,
            "PatchPilot finished installing updates for:\n\n"
            "- `update.core`\n\n"
            "Restart Home Assistant to finish applying these updates:\n\n"
            "- `update.core`\n\n"
            "PatchPilot did not install these pending updates:\n\n"
            "Filtered by PatchPilot configuration:\n- `update.router`",
        )


class BuildUpdatesInstalledNotificationTests(unittest.TestCase):
    """Test the updates-installed notification."""

    def test_title_and_body_without_skipped(self) -> None:
        title, message = build_updates_installed_notification(
            ["update.router"], [], [], {"update.router": "Router"}
        )
        self.assertEqual(title, "PatchPilot updates installed")
        self.assertEqual(
            message,
            "PatchPilot finished installing updates for:\n\n"
            "- Router (`update.router`)\n\n"
            "PatchPilot did not detect a Home Assistant restart requirement "
            "for these update entities.",
        )

    def test_appends_skipped_tail(self) -> None:
        _title, message = build_updates_installed_notification(
            ["update.router"], [], ["update.hacs"], {}
        )
        self.assertTrue(
            message.endswith(
                "\n\nPatchPilot did not install these pending updates:\n\n"
                "Pending but not installable through Home Assistant:\n"
                "- `update.hacs`"
            )
        )


class BuildSkippedUpdatesNotificationTests(unittest.TestCase):
    """Test the skipped-updates notification."""

    def test_title_and_body(self) -> None:
        title, message = build_skipped_updates_notification(
            ["update.router"], ["update.hacs"], {"update.router": "Router"}
        )
        self.assertEqual(title, "PatchPilot skipped updates")
        self.assertEqual(
            message,
            "PatchPilot will not install these pending updates:\n\n"
            "Filtered by PatchPilot configuration:\n"
            "- Router (`update.router`)\n\n"
            "Pending but not installable through Home Assistant:\n"
            "- `update.hacs`",
        )


if __name__ == "__main__":
    unittest.main()
