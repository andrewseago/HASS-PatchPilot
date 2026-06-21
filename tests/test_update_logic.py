"""Tests for PatchPilot pure update logic."""

from __future__ import annotations

from datetime import time
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "patchpilot"
    / "update_logic.py"
)
SPEC = importlib.util.spec_from_file_location("patchpilot_update_logic", MODULE_PATH)
assert SPEC is not None
update_logic = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = update_logic
SPEC.loader.exec_module(update_logic)

UpdateCandidate = update_logic.UpdateCandidate
is_allowed_entity = update_logic.is_allowed_entity
is_time_in_window = update_logic.is_time_in_window
parse_time = update_logic.parse_time
requires_home_assistant_restart = getattr(
    update_logic, "requires_home_assistant_restart", None
)
select_pending_updates = update_logic.select_pending_updates
summarize_update_candidates = update_logic.summarize_update_candidates
flatten_sectioned_input = update_logic.flatten_sectioned_input
select_retry_entities = update_logic.select_retry_entities


class UpdateLogicTests(unittest.TestCase):
    """Test update selection helpers."""

    def test_parse_time(self) -> None:
        self.assertEqual(parse_time("03:04"), time(3, 4, 0))
        self.assertEqual(parse_time("03:04:05"), time(3, 4, 5))

    def test_parse_time_rejects_invalid_values(self) -> None:
        for value in ("3", "25:00", "03:70", "03:04:70"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_time(value)

    def test_maintenance_window_same_day(self) -> None:
        self.assertTrue(is_time_in_window(time(3, 30), time(3), time(5)))
        self.assertFalse(is_time_in_window(time(2, 59), time(3), time(5)))
        self.assertFalse(is_time_in_window(time(5), time(3), time(5)))

    def test_maintenance_window_crosses_midnight(self) -> None:
        self.assertTrue(is_time_in_window(time(23, 30), time(22), time(2)))
        self.assertTrue(is_time_in_window(time(1, 30), time(22), time(2)))
        self.assertFalse(is_time_in_window(time(3), time(22), time(2)))

    def test_pattern_allow_list(self) -> None:
        self.assertTrue(is_allowed_entity("update.hacs", ["update.*"], []))
        self.assertFalse(
            is_allowed_entity("update.router", ["update.*"], ["update.router"])
        )

    def test_select_pending_installable_updates(self) -> None:
        install_feature = 1
        candidates = [
            UpdateCandidate("update.core", "on", install_feature),
            UpdateCandidate("update.os", "off", install_feature),
            UpdateCandidate("update.hacs", "on", 0),
            UpdateCandidate("update.router", "on", install_feature),
        ]
        selected = select_pending_updates(
            candidates,
            ["update.*"],
            ["update.router"],
            [],
            install_feature,
        )
        self.assertEqual(
            [candidate.entity_id for candidate in selected], ["update.core"]
        )

    def test_select_respects_exact_exclusions(self) -> None:
        install_feature = 1
        candidates = [
            UpdateCandidate("update.core", "on", install_feature),
            UpdateCandidate("update.hacs", "on", install_feature),
        ]
        selected = select_pending_updates(
            candidates,
            ["update.*"],
            [],
            ["update.hacs"],
            install_feature,
        )
        self.assertEqual(
            [candidate.entity_id for candidate in selected], ["update.core"]
        )

    def test_summary_separates_pending_from_installable_updates(self) -> None:
        install_feature = 1
        candidates = [
            UpdateCandidate("update.core", "on", install_feature),
            UpdateCandidate("update.hacs", "on", 0),
            UpdateCandidate("update.router", "on", install_feature),
            UpdateCandidate("update.idle", "off", install_feature),
        ]

        summary = summarize_update_candidates(
            candidates,
            ["update.*"],
            ["update.router"],
            [],
            install_feature,
            0,
        )

        self.assertEqual(
            [candidate.entity_id for candidate in summary.pending],
            ["update.core", "update.hacs", "update.router"],
        )
        self.assertEqual(
            [candidate.entity_id for candidate in summary.installable],
            ["update.core"],
        )
        self.assertEqual(
            [candidate.entity_id for candidate in summary.uninstallable],
            ["update.hacs"],
        )
        self.assertEqual(
            [candidate.entity_id for candidate in summary.filtered],
            ["update.router"],
        )

    def test_restart_required_classification_is_conservative(self) -> None:
        self.assertIsNotNone(requires_home_assistant_restart)
        assert requires_home_assistant_restart is not None

        self.assertTrue(
            requires_home_assistant_restart(
                "update.opnsense_integration_for_home_assistant_update", "hacs"
            )
        )
        self.assertTrue(
            requires_home_assistant_restart(
                "update.home_assistant_core_update", "hassio"
            )
        )
        self.assertFalse(
            requires_home_assistant_restart(
                "update.opnsense_firmware_updates_available", "opnsense"
            )
        )
        self.assertFalse(
            requires_home_assistant_restart(
                "update.pi_hole_web_update_available", "pi_hole"
            )
        )


class RetrySelectionTests(unittest.TestCase):
    """Test retry entity selection from a run result's failed mapping."""

    def test_none_failed_returns_empty_list(self) -> None:
        self.assertEqual(select_retry_entities(None), [])

    def test_empty_failed_returns_empty_list(self) -> None:
        self.assertEqual(select_retry_entities({}), [])

    def test_failed_mapping_returns_sorted_entity_ids(self) -> None:
        failed = {
            "update.router": "timeout",
            "update.core": "install failed",
            "update.hacs": "offline",
        }
        self.assertEqual(
            select_retry_entities(failed),
            ["update.core", "update.hacs", "update.router"],
        )

    def test_single_failed_entity(self) -> None:
        self.assertEqual(
            select_retry_entities({"update.core": "boom"}),
            ["update.core"],
        )


class FlattenSectionedInputTests(unittest.TestCase):
    """Test flattening of Home Assistant config-flow sectioned input."""

    section_map = {
        "schedule": (
            "enabled",
            "check_interval_minutes",
            "window_start",
            "window_end",
        ),
        "what_to_update": (
            "include_patterns",
            "exclude_patterns",
            "excluded_entities",
        ),
        "install_behavior": (
            "create_backup",
            "max_updates_per_run",
        ),
        "notifications_history": (
            "run_on_state_change",
            "notify_on_failure",
            "log_size",
        ),
    }

    def test_nested_sections_are_flattened(self) -> None:
        user_input = {
            "schedule": {
                "enabled": True,
                "check_interval_minutes": 30,
                "window_start": "03:00:00",
                "window_end": "05:00:00",
            },
            "what_to_update": {
                "include_patterns": ["update.*"],
                "exclude_patterns": [],
                "excluded_entities": ["update.router"],
            },
            "install_behavior": {
                "create_backup": True,
                "max_updates_per_run": 5,
            },
            "notifications_history": {
                "run_on_state_change": False,
                "notify_on_failure": True,
                "log_size": 50,
            },
        }
        self.assertEqual(
            flatten_sectioned_input(user_input, self.section_map),
            {
                "enabled": True,
                "check_interval_minutes": 30,
                "window_start": "03:00:00",
                "window_end": "05:00:00",
                "include_patterns": ["update.*"],
                "exclude_patterns": [],
                "excluded_entities": ["update.router"],
                "create_backup": True,
                "max_updates_per_run": 5,
                "run_on_state_change": False,
                "notify_on_failure": True,
                "log_size": 50,
            },
        )

    def test_already_flat_input_is_idempotent(self) -> None:
        flat = {
            "enabled": True,
            "check_interval_minutes": 30,
            "window_start": "03:00:00",
            "window_end": "05:00:00",
            "include_patterns": ["update.*"],
            "max_updates_per_run": 5,
        }
        self.assertEqual(
            flatten_sectioned_input(flat, self.section_map),
            flat,
        )

    def test_stray_top_level_keys_pass_through(self) -> None:
        user_input = {
            "schedule": {
                "enabled": True,
                "check_interval_minutes": 30,
            },
            "name": "PatchPilot",
            "max_updates_per_run": 3,
        }
        self.assertEqual(
            flatten_sectioned_input(user_input, self.section_map),
            {
                "enabled": True,
                "check_interval_minutes": 30,
                "name": "PatchPilot",
                "max_updates_per_run": 3,
            },
        )

    def test_empty_input_returns_empty_dict(self) -> None:
        self.assertEqual(flatten_sectioned_input({}, self.section_map), {})


if __name__ == "__main__":
    unittest.main()
