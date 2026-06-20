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
select_pending_updates = update_logic.select_pending_updates
summarize_update_candidates = update_logic.summarize_update_candidates


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


if __name__ == "__main__":
    unittest.main()
