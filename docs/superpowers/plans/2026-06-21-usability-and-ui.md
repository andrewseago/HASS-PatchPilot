# PatchPilot Usability & UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A coordinated usability and UI pass across PatchPilot's config flow, entities, notifications, and repairs, plus documented dashboard YAML — additive, pure-Python, no behavior change to update selection.

**Architecture:** Keep PatchPilot's core rule — testable logic lives in stdlib-only helper modules (`update_logic.py`, new `presentation.py`), HA-coupled glue stays thin. Config-flow gets collapsible sections + native time pickers; entities move to `translation_key` + `icons.json` and gain a "Restart required" binary sensor; notifications resolve friendly names and build text in the pure `presentation.py`; the failed-run repair issue becomes fixable with a retry/dismiss flow.

**Tech Stack:** Python 3.13, Home Assistant 2026.6.0 custom-integration APIs (`data_entry_flow.section`, `selector.TimeSelector`, `icons.json` icon translations, `homeassistant.components.repairs.RepairsFlow`, `homeassistant.helpers.issue_registry`, `persistent_notification.async_create`). Tests are pure (unittest + pytest), no HA runtime harness. pre-commit: pyupgrade --py313-plus, black, isort, flake8.

## Global Constraints

- **Target/minimum HA version: 2026.6.0** (every API used is ≤ 2024.7; ample headroom). Do not raise `hacs.json`'s `homeassistant` baseline.
- **Version: bump `0.3.8` → `0.4.0`** in exactly four locations — `custom_components/patchpilot/manifest.json`, `pyproject.toml`, `CHANGELOG.md`, and `EXPECTED_VERSION` in `tests/test_project_structure.py`. A test pins all four.
- **Two-file string discipline:** `custom_components/patchpilot/strings.json` and `custom_components/patchpilot/translations/en.json` must stay **byte-identical** (custom integrations load `en.json` at runtime). After editing `strings.json`, regenerate with `cp custom_components/patchpilot/strings.json custom_components/patchpilot/translations/en.json`. The test `test_custom_component_translation_is_packaged` asserts deep-equality.
- **Pure helper modules import stdlib only** — `update_logic.py` and `presentation.py` must never import `homeassistant`; tests load them by file path via `importlib`.
- **No update-selection behavior change.** `summarize_update_candidates`, window/debounce/install logic keep current semantics.
- **No `DataUpdateCoordinator` refactor; no custom JS card.**
- **Commit style:** short imperative, no conventional-commit prefix (repo style: "Add …", "Group …", "Bump …").
- **Per-task verification:** `python3 -m compileall -q custom_components`; JSON validity via `python3 -m json.tool`; `pytest -q`. CI also runs `pre-commit run --all-files`, HACS validation, and Hassfest.

### Shared-file coordination (read before starting)

Two files are edited by multiple tasks. Apply tasks in the numbered order below and these stay conflict-free:

- **`strings.json` / `translations/en.json`** — edited by **Task 3** (config-flow: full rewrite of `config`+`options` blocks), **Task 4** (entities: appends a top-level `entity` block), and **Task 9** (repairs: replaces the `issues.last_run_failed` block with a `fix_flow` form). Order is mandatory: 3 → 4 → 9. After Task 4 appends `entity`, the `issues` block is **no longer the last** top-level key — Task 9 must preserve surrounding commas accordingly.
- **`tests/test_project_structure.py`** — edited by Tasks 3, 4, 6, 7, 8, 9, 11, 12. Each makes a **distinct, localized** edit (a new function, a constant, the expected-files tuple, or one assertion). Applied in order they do not collide. Each task's step text says exactly which lines it owns.

### Task dependency order

```
1  pure helpers (update_logic)
2  presentation.py (pure builders)
3  config-flow sections + time pickers        [strings.json rewrite]
4  entities → translation_key + icons.json    [strings.json append] [needs 1? no — independent]
5  restart-required binary_sensor             [needs 4]
6  manager: friendly names + presentation     [needs 2; relocates structural asserts]
7  manager: retry entry point + fixable issue [needs 1, 6]
8  repairs.py fix flow                         [needs 7; strings.json issues block]
9  version bump 0.4.0
10 structural tests for new files + icons      [needs 2,4,5,8]
11 dashboard + restart-sensor docs
12 final verification
```

`presentation.py` (2) and `update_logic` helpers (1) are independent and can be done first in either order. Tasks 3 and 4 both touch `strings.json`, so 3 precedes 4. Everything else follows the arrows.

---

### Task 1: Pure helpers for sectioned-input flattening and retry selection

**Files:**
- Modify: `custom_components/patchpilot/update_logic.py`
- Test: `tests/test_update_logic.py`

**Interfaces:**
- Consumes: nothing new (pure stdlib; no `homeassistant` imports).
- Produces:
  - `flatten_sectioned_input(user_input: dict[str, Any], section_map: dict[str, tuple[str, ...]]) -> dict[str, Any]`
  - `select_retry_entities(failed: dict[str, str] | None) -> list[str]`

These are the testable seam the feature builds on: the config-flow task (Task 3) calls `flatten_sectioned_input` to collapse HA "sections" output before the existing `_validate_input`/`_normalize_input`; the manager retry path (Task 7) calls `select_retry_entities` to turn a run result's `failed` mapping into an ordered list.

- [ ] **Step 1: Wire up the test module attributes.** In `tests/test_update_logic.py`, after the line `summarize_update_candidates = update_logic.summarize_update_candidates` (line 32), add:

```python
flatten_sectioned_input = update_logic.flatten_sectioned_input
select_retry_entities = update_logic.select_retry_entities
```

- [ ] **Step 2: Write the failing test for `select_retry_entities`.** Append before the `if __name__ == "__main__":` block (line 161):

```python
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
```

- [ ] **Step 3: Run the test to verify it fails.**

Run: `pytest tests/test_update_logic.py::RetrySelectionTests -v`
Expected: FAIL at import — `AttributeError: module 'patchpilot_update_logic' has no attribute 'select_retry_entities'`.

- [ ] **Step 4: Implement `select_retry_entities`.** Append to the end of `custom_components/patchpilot/update_logic.py`:

```python
def select_retry_entities(failed: dict[str, str] | None) -> list[str]:
    """Return the sorted entity ids to retry from a run result's failures."""
    if not failed:
        return []
    return sorted(failed)
```

- [ ] **Step 5: Run the test to verify it passes.**

Run: `pytest tests/test_update_logic.py::RetrySelectionTests -v`
Expected: 4 passed.

- [ ] **Step 6: Commit.**

```bash
git add custom_components/patchpilot/update_logic.py tests/test_update_logic.py
git commit -m "Add retry entity selection helper"
```

- [ ] **Step 7: Write the failing test for `flatten_sectioned_input`.** Append after `RetrySelectionTests`, before `if __name__ == "__main__":`:

```python
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
```

- [ ] **Step 8: Run the test to verify it fails.**

Run: `pytest tests/test_update_logic.py::FlattenSectionedInputTests -v`
Expected: FAIL at import — `AttributeError: module 'patchpilot_update_logic' has no attribute 'flatten_sectioned_input'`.

- [ ] **Step 9: Add the `Any` import.** In `custom_components/patchpilot/update_logic.py`, after `from fnmatch import fnmatchcase` (line 8) add:

```python
from typing import Any
```

- [ ] **Step 10: Implement `flatten_sectioned_input`.** Append to the end of `custom_components/patchpilot/update_logic.py`:

```python
def flatten_sectioned_input(
    user_input: dict[str, Any],
    section_map: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    """Flatten Home Assistant config-flow sectioned input to a flat dict.

    Keys that are section names in ``section_map`` have their listed child
    fields lifted to the top level; any other key is copied through unchanged,
    so already-flat input is handled idempotently.
    """
    flat: dict[str, Any] = {}
    for key, value in user_input.items():
        fields = section_map.get(key)
        if fields is not None and isinstance(value, Mapping):
            for field in fields:
                if field in value:
                    flat[field] = value[field]
        else:
            flat[key] = value
    return flat
```

(`Mapping` is already imported on line 6.)

- [ ] **Step 11: Run the test to verify it passes.**

Run: `pytest tests/test_update_logic.py::FlattenSectionedInputTests -v`
Expected: 4 passed.

- [ ] **Step 12: Run the whole module to confirm no regressions.**

Run: `pytest tests/test_update_logic.py -v`
Expected: all pass (`UpdateLogicTests` + `RetrySelectionTests` + `FlattenSectionedInputTests`).

- [ ] **Step 13: Commit.**

```bash
git add custom_components/patchpilot/update_logic.py tests/test_update_logic.py
git commit -m "Add sectioned-input flattening helper"
```

---

### Task 2: Pure notification builders (presentation.py)

**Files:**
- Create: `custom_components/patchpilot/presentation.py`
- Test: `tests/test_presentation.py`

**Interfaces:**
- Consumes: nothing (pure stdlib).
- Produces (all pure; every builder returns `tuple[str, str]` = `(title, message)`):
  - `format_entity(entity_id: str, names: dict[str, str]) -> str`
  - `format_skipped_sections(filtered: list[str], uninstallable: list[str], names: dict[str, str]) -> str`
  - `build_failure_notification(failed: dict[str, str], names: dict[str, str]) -> tuple[str, str]`
  - `build_restart_required_notification(installed: list[str], restart_required: list[str], filtered: list[str], uninstallable: list[str], names: dict[str, str]) -> tuple[str, str]`
  - `build_updates_installed_notification(installed: list[str], filtered: list[str], uninstallable: list[str], names: dict[str, str]) -> tuple[str, str]`
  - `build_skipped_updates_notification(filtered: list[str], uninstallable: list[str], names: dict[str, str]) -> tuple[str, str]`

The title literals (`"PatchPilot restart required"`, etc.) and skipped-section labels live here, not in `manager.py`.

- [ ] **Step 1: Write the test loader + `format_entity` test.** Create `tests/test_presentation.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails.**

Run: `pytest tests/test_presentation.py -v`
Expected: FAIL — `FileNotFoundError`/import error (presentation.py does not exist).

- [ ] **Step 3: Create `presentation.py` with the header, `format_entity`, and `_format_entity_list`.** Create `custom_components/patchpilot/presentation.py`:

```python
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
    return "\n".join(
        f"- {format_entity(entity_id, names)}" for entity_id in entity_ids
    )
```

- [ ] **Step 4: Run to verify `format_entity` tests pass.**

Run: `pytest tests/test_presentation.py::FormatEntityTests -v`
Expected: 2 passed.

- [ ] **Step 5: Add the `format_skipped_sections` test.** Append before `if __name__`:

```python
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
```

- [ ] **Step 6: Run to verify it fails.**

Run: `pytest tests/test_presentation.py::FormatSkippedSectionsTests -v`
Expected: FAIL — `AttributeError: ... 'format_skipped_sections'`.

- [ ] **Step 7: Implement `format_skipped_sections`.** Append to `presentation.py` (labels are byte-identical to the old manager helper):

```python
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
```

- [ ] **Step 8: Run to verify it passes.**

Run: `pytest tests/test_presentation.py::FormatSkippedSectionsTests -v`
Expected: 4 passed.

- [ ] **Step 9: Add the `build_failure_notification` test.** Append before `if __name__`:

```python
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
```

- [ ] **Step 10: Run to verify it fails, then implement.**

Run: `pytest tests/test_presentation.py::BuildFailureNotificationTests -v` → FAIL. Then append to `presentation.py`:

```python
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
```

Run again: 1 passed.

- [ ] **Step 11: Add the `build_restart_required_notification` test.** Append before `if __name__`:

```python
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
```

- [ ] **Step 12: Run to verify it fails, then implement.**

Run: `pytest tests/test_presentation.py::BuildRestartRequiredNotificationTests -v` → FAIL. Then append to `presentation.py`:

```python
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
```

Run again: 2 passed.

- [ ] **Step 13: Add the `build_updates_installed_notification` test.** Append before `if __name__`:

```python
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
```

- [ ] **Step 14: Run to verify it fails, then implement.**

Run: `pytest tests/test_presentation.py::BuildUpdatesInstalledNotificationTests -v` → FAIL. Then append to `presentation.py`:

```python
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
```

Run again: 2 passed.

- [ ] **Step 15: Add the `build_skipped_updates_notification` test.** Append before `if __name__`:

```python
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
```

- [ ] **Step 16: Run to verify it fails, then implement.**

Run: `pytest tests/test_presentation.py::BuildSkippedUpdatesNotificationTests -v` → FAIL. Then append to `presentation.py`:

```python
def build_skipped_updates_notification(
    filtered: list[str], uninstallable: list[str], names: dict[str, str]
) -> tuple[str, str]:
    """Build the (title, message) listing skipped pending updates."""
    sections = format_skipped_sections(filtered, uninstallable, names)
    message = f"PatchPilot will not install these pending updates:\n\n{sections}"
    return "PatchPilot skipped updates", message
```

- [ ] **Step 17: Run the whole file and commit.**

Run: `pytest tests/test_presentation.py -v`
Expected: all pass.

```bash
git add custom_components/patchpilot/presentation.py tests/test_presentation.py
git commit -m "Add pure notification builders module"
```

---

### Task 3: Group config/options flow into sections with native time pickers

> **Shared-file note:** This is the FIRST of three tasks that edit `strings.json`/`en.json`. It does a full rewrite of the `config` and `options` blocks. Tasks 4 (entity block) and 9 (issues block) come after.

**Files:**
- Modify: `custom_components/patchpilot/config_flow.py`
- Modify: `custom_components/patchpilot/strings.json`, `custom_components/patchpilot/translations/en.json`
- Test: `tests/test_project_structure.py` (add one new function)

**Interfaces:**
- Consumes: `flatten_sectioned_input` (Task 1) — `from .update_logic import flatten_sectioned_input, parse_time`.
- Produces: module-level `SECTION_MAP` constant; sectioned `_schema`; `async_step_user`/`async_step_init` flatten input before validation.

- [ ] **Step 1: Write the failing structural test.** Append to the end of `tests/test_project_structure.py`:

```python
def test_config_flow_groups_fields_into_sections_with_time_pickers() -> None:
    """The config/options flow should use collapsible sections and time pickers."""
    config_flow_source = (INTEGRATION_DIR / "config_flow.py").read_text()
    strings = json.loads((INTEGRATION_DIR / "strings.json").read_text())

    assert "from homeassistant.data_entry_flow import section" in config_flow_source
    assert "TimeSelector" in config_flow_source
    assert "TimeSelector()" in config_flow_source
    assert "flatten_sectioned_input" in config_flow_source
    assert "SECTION_MAP" in config_flow_source
    assert "section(" in config_flow_source
    assert '"collapsed": True' in config_flow_source
    assert '"collapsed": False' in config_flow_source

    for top in ("config", "options"):
        step = "user" if top == "config" else "init"
        sections = strings[top]["step"][step]["sections"]
        assert set(sections) == {
            "schedule",
            "what_to_update",
            "install_behavior",
            "notifications_history",
        }
        assert sections["schedule"]["data"]["window_start"]
        assert sections["schedule"]["data"]["window_end"]
        assert "0 means no limit." in (
            sections["install_behavior"]["data_description"]["max_updates_per_run"]
        )
        assert "0 disables run history." in (
            sections["notifications_history"]["data_description"]["log_size"]
        )
```

- [ ] **Step 2: Run to verify it fails.**

Run: `pytest tests/test_project_structure.py -q -k groups_fields_into_sections`
Expected: FAIL — `KeyError: 'sections'` (or the `section` import assertion).

- [ ] **Step 3: Update imports in `config_flow.py`.** After the `from homeassistant.core import callback` line (line 8) add `from homeassistant.data_entry_flow import section`. Add `TimeSelector` to the `homeassistant.helpers.selector` import block. Change the `update_logic` import (line 48) to:

```python
from .update_logic import flatten_sectioned_input, parse_time
```

Resulting selector import block:

```python
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TimeSelector,
)
```

- [ ] **Step 4: Add the `SECTION_MAP` constant.** In `config_flow.py`, immediately after the `from .update_logic import ...` line and before `class PatchPilotConfigFlow`:

```python
SECTION_MAP = {
    "schedule": (
        CONF_ENABLED,
        CONF_CHECK_INTERVAL_MINUTES,
        CONF_WINDOW_START,
        CONF_WINDOW_END,
    ),
    "what_to_update": (
        CONF_INCLUDE_PATTERNS,
        CONF_EXCLUDE_PATTERNS,
        CONF_EXCLUDED_ENTITIES,
    ),
    "install_behavior": (
        CONF_CREATE_BACKUP,
        CONF_MAX_UPDATES_PER_RUN,
    ),
    "notifications_history": (
        CONF_RUN_ON_STATE_CHANGE,
        CONF_NOTIFY_ON_FAILURE,
        CONF_LOG_SIZE,
    ),
}
```

(The `CONF_*` constants equal the bare field-name strings, so this matches `flatten_sectioned_input`'s `section_map` contract.)

- [ ] **Step 5: Flatten input in `async_step_user`.** Replace:

```python
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_input(user_input)
```

with:

```python
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = flatten_sectioned_input(user_input, SECTION_MAP)
            errors = _validate_input(user_input)
```

- [ ] **Step 6: Flatten input in `async_step_init`.** Replace:

```python
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            errors = _validate_input(user_input)
```

with:

```python
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            user_input = flatten_sectioned_input(user_input, SECTION_MAP)
            errors = _validate_input(user_input)
```

- [ ] **Step 7: Rewrite `_schema` to build a sectioned schema.** Replace the entire `_schema` function (lines 112-187) with:

```python
def _schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Return config/options schema grouped into collapsible sections."""
    values = values or {}
    return vol.Schema(
        {
            vol.Required("schedule"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_ENABLED,
                            default=values.get(CONF_ENABLED, DEFAULT_ENABLED),
                        ): BooleanSelector(),
                        vol.Optional(
                            CONF_CHECK_INTERVAL_MINUTES,
                            default=values.get(
                                CONF_CHECK_INTERVAL_MINUTES,
                                DEFAULT_CHECK_INTERVAL_MINUTES,
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=5,
                                max=1440,
                                mode=NumberSelectorMode.BOX,
                                unit_of_measurement="min",
                            )
                        ),
                        vol.Optional(
                            CONF_WINDOW_START,
                            default=values.get(
                                CONF_WINDOW_START, DEFAULT_WINDOW_START
                            ),
                        ): TimeSelector(),
                        vol.Optional(
                            CONF_WINDOW_END,
                            default=values.get(CONF_WINDOW_END, DEFAULT_WINDOW_END),
                        ): TimeSelector(),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required("what_to_update"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_INCLUDE_PATTERNS,
                            default=_patterns_to_text(
                                values.get(
                                    CONF_INCLUDE_PATTERNS, DEFAULT_INCLUDE_PATTERNS
                                )
                            ),
                        ): TextSelector(TextSelectorConfig(multiline=True)),
                        vol.Optional(
                            CONF_EXCLUDE_PATTERNS,
                            default=_patterns_to_text(
                                values.get(
                                    CONF_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_PATTERNS
                                )
                            ),
                        ): TextSelector(TextSelectorConfig(multiline=True)),
                        vol.Optional(
                            CONF_EXCLUDED_ENTITIES,
                            default=values.get(
                                CONF_EXCLUDED_ENTITIES, DEFAULT_EXCLUDED_ENTITIES
                            ),
                        ): EntitySelector(
                            EntitySelectorConfig(domain="update", multiple=True)
                        ),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required("install_behavior"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_CREATE_BACKUP,
                            default=values.get(
                                CONF_CREATE_BACKUP, DEFAULT_CREATE_BACKUP
                            ),
                        ): BooleanSelector(),
                        vol.Optional(
                            CONF_MAX_UPDATES_PER_RUN,
                            default=values.get(
                                CONF_MAX_UPDATES_PER_RUN,
                                DEFAULT_MAX_UPDATES_PER_RUN,
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=0, max=100, mode=NumberSelectorMode.BOX
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("notifications_history"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_RUN_ON_STATE_CHANGE,
                            default=values.get(
                                CONF_RUN_ON_STATE_CHANGE,
                                DEFAULT_RUN_ON_STATE_CHANGE,
                            ),
                        ): BooleanSelector(),
                        vol.Optional(
                            CONF_NOTIFY_ON_FAILURE,
                            default=values.get(
                                CONF_NOTIFY_ON_FAILURE, DEFAULT_NOTIFY_ON_FAILURE
                            ),
                        ): BooleanSelector(),
                        vol.Optional(
                            CONF_LOG_SIZE,
                            default=values.get(CONF_LOG_SIZE, DEFAULT_LOG_SIZE),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=0, max=100, mode=NumberSelectorMode.BOX
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )
```

(The helpers `_validate_input`, `_normalize_input`, `_patterns_to_list`, `_patterns_to_text` below `_schema` are unchanged — they operate on the flat dict produced by `flatten_sectioned_input`.)

- [ ] **Step 8: Rewrite `strings.json`.** Replace the entire file contents with:

```json
{
  "title": "PatchPilot",
  "config": {
    "step": {
      "user": {
        "title": "PatchPilot",
        "description": "Pilot Home Assistant updates automatically during a maintenance window.",
        "sections": {
          "schedule": {
            "name": "Schedule",
            "description": "When PatchPilot checks for and installs updates.",
            "data": {
              "enabled": "Enable automatic updates",
              "check_interval_minutes": "Check interval",
              "window_start": "Maintenance window start",
              "window_end": "Maintenance window end"
            },
            "data_description": {
              "window_start": "Updates only install between this time and the window end.",
              "window_end": "End of the maintenance window."
            }
          },
          "what_to_update": {
            "name": "What to update",
            "description": "Choose which update entities PatchPilot manages.",
            "data": {
              "include_patterns": "Include entity patterns",
              "exclude_patterns": "Exclude entity patterns",
              "excluded_entities": "Excluded update entities"
            },
            "data_description": {
              "include_patterns": "One shell-style glob per line, e.g. update.* or update.router*.",
              "exclude_patterns": "One shell-style glob per line, e.g. update.* or update.router*."
            }
          },
          "install_behavior": {
            "name": "Install behavior",
            "description": "How PatchPilot installs updates during a run.",
            "data": {
              "create_backup": "Create backups when supported",
              "max_updates_per_run": "Maximum updates per run"
            },
            "data_description": {
              "max_updates_per_run": "0 means no limit."
            }
          },
          "notifications_history": {
            "name": "Notifications and history",
            "description": "Run triggers, failure alerts, and run history.",
            "data": {
              "run_on_state_change": "Run when updates appear",
              "notify_on_failure": "Notify on failure",
              "log_size": "Run history size"
            },
            "data_description": {
              "log_size": "0 disables run history."
            }
          }
        }
      }
    },
    "error": {
      "invalid_time": "Use HH:MM or HH:MM:SS.",
      "empty_include_patterns": "At least one include pattern is required."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "PatchPilot options",
        "sections": {
          "schedule": {
            "name": "Schedule",
            "description": "When PatchPilot checks for and installs updates.",
            "data": {
              "enabled": "Enable automatic updates",
              "check_interval_minutes": "Check interval",
              "window_start": "Maintenance window start",
              "window_end": "Maintenance window end"
            },
            "data_description": {
              "window_start": "Updates only install between this time and the window end.",
              "window_end": "End of the maintenance window."
            }
          },
          "what_to_update": {
            "name": "What to update",
            "description": "Choose which update entities PatchPilot manages.",
            "data": {
              "include_patterns": "Include entity patterns",
              "exclude_patterns": "Exclude entity patterns",
              "excluded_entities": "Excluded update entities"
            },
            "data_description": {
              "include_patterns": "One shell-style glob per line, e.g. update.* or update.router*.",
              "exclude_patterns": "One shell-style glob per line, e.g. update.* or update.router*."
            }
          },
          "install_behavior": {
            "name": "Install behavior",
            "description": "How PatchPilot installs updates during a run.",
            "data": {
              "create_backup": "Create backups when supported",
              "max_updates_per_run": "Maximum updates per run"
            },
            "data_description": {
              "max_updates_per_run": "0 means no limit."
            }
          },
          "notifications_history": {
            "name": "Notifications and history",
            "description": "Run triggers, failure alerts, and run history.",
            "data": {
              "run_on_state_change": "Run when updates appear",
              "notify_on_failure": "Notify on failure",
              "log_size": "Run history size"
            },
            "data_description": {
              "log_size": "0 disables run history."
            }
          }
        }
      }
    },
    "error": {
      "invalid_time": "Use HH:MM or HH:MM:SS.",
      "empty_include_patterns": "At least one include pattern is required."
    }
  },
  "issues": {
    "last_run_failed": {
      "title": "PatchPilot failed to install updates",
      "description": "{count} update entity or entities failed during the last update run: {entities}. Check the Home Assistant log for details."
    }
  }
}
```

- [ ] **Step 9: Regenerate `en.json` byte-identically.**

```bash
cp custom_components/patchpilot/strings.json custom_components/patchpilot/translations/en.json
```

- [ ] **Step 10: Run the new test + compile + JSON checks.**

Run:
```bash
pytest tests/test_project_structure.py -q -k groups_fields_into_sections
python3 -m compileall -q custom_components
python3 -m json.tool custom_components/patchpilot/strings.json > /dev/null
python3 -m json.tool custom_components/patchpilot/translations/en.json > /dev/null
```
Expected: test passes; compile silent; JSON valid.

- [ ] **Step 11: Run the full structure suite.**

Run: `pytest tests/test_project_structure.py -q`
Expected: all pass (including `test_custom_component_translation_is_packaged`).

- [ ] **Step 12: Commit.**

```bash
git add custom_components/patchpilot/config_flow.py custom_components/patchpilot/strings.json custom_components/patchpilot/translations/en.json tests/test_project_structure.py
git commit -m "Group config flow fields into collapsible sections with time pickers"
```

---

### Task 4: Migrate entities to translation keys and icons.json

> **Shared-file note:** SECOND task editing `strings.json`/`en.json` — it APPENDS a top-level `entity` block after `issues`. Must run after Task 3.

**Files:**
- Modify: `custom_components/patchpilot/entity.py`, `sensor.py`, `button.py`, `switch.py`
- Create: `custom_components/patchpilot/icons.json`
- Modify: `custom_components/patchpilot/strings.json`, `custom_components/patchpilot/translations/en.json`

**Interfaces:**
- Consumes: nothing new from `manager`.
- Produces: base `PatchPilotEntity.__init__(self, manager, key)` / `PatchPilotObservableEntity.__init__(self, manager, key)` set `self._attr_translation_key = key` and `self._attr_unique_id = f"{manager.entry.entry_id}_{key}"`, no `_attr_name`. `PatchPilotButton.__init__(self, manager, key)` drops the icon arg. `icons.json` maps every translation key (incl. `binary_sensor.restart_required`, authored here for Task 5). Class names/bases UNCHANGED so `test_entities_share_patchpilot_device_info` stays green.

> This task adds NO new test functions and does NOT edit the PLATFORMS assertion (that is Task 5). It keeps existing structural tests green by editing `strings.json` + `en.json` identically.

- [ ] **Step 1: Rewrite `entity.py`.** Replace the full file:

```python
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
```

- [ ] **Step 2: Update `sensor.py`.** Change `PatchPilotSensor.__init__` to drop `name`, and remove every `_attr_icon` line plus the name argument from each subclass call:
  - `PatchPilotSensor.__init__`:
    ```python
    def __init__(self, manager: PatchPilotManager, key: str) -> None:
        """Initialize sensor."""
        super().__init__(manager, key)
    ```
  - Delete `_attr_icon = "mdi:update"` (PendingUpdatesSensor); call → `super().__init__(manager, "pending_updates")`.
  - Delete `_attr_icon = "mdi:package-up"` (InstallableUpdatesSensor); call → `super().__init__(manager, "installable_updates")`.
  - Delete `_attr_icon = "mdi:update-off"` (SkippedUpdatesSensor); call → `super().__init__(manager, "skipped_updates")`.
  - Delete `_attr_icon = "mdi:clock-check-outline"` (LastRunSensor; KEEP `_attr_device_class = SensorDeviceClass.TIMESTAMP`); call → `super().__init__(manager, "last_run")`.
  - Delete `_attr_icon = "mdi:package-up"` (LastInstalledCountSensor); call → `super().__init__(manager, "last_installed_count")`.
  - Delete `_attr_icon = "mdi:alert-circle-outline"` (LastFailedCountSensor); call → `super().__init__(manager, "last_failed_count")`.
  - Delete `_attr_icon = "mdi:history"` (RunHistorySensor); call → `super().__init__(manager, "run_history")`.

- [ ] **Step 3: Update `button.py`.** Drop the `icon` parameter and `_attr_icon` from the base; remove icon+name from each subclass call. `async_press` bodies UNCHANGED:

```python
class PatchPilotButton(PatchPilotEntity, ButtonEntity):
    """Base PatchPilot button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager: PatchPilotManager, key: str) -> None:
        """Initialize button."""
        super().__init__(manager, key)
```
  - `ScanUpdatesButton` call → `super().__init__(manager, "scan_updates")`
  - `DryRunButton` call → `super().__init__(manager, "dry_run")`
  - `RunUpdatesButton` call → `super().__init__(manager, "run_updates_now")`
  - Leave `reason="button_dry_run"`, `dry_run=True`, `ignore_window=True`, `reason="button"` exactly as-is.

- [ ] **Step 4: Update `switch.py`.** Delete `_attr_icon = "mdi:auto-fix"`; drop the name:

```python
class PatchPilotSwitch(PatchPilotObservableEntity, SwitchEntity):
    """Switch automatic PatchPilot update runs on or off."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize switch."""
        super().__init__(manager, "automatic_updates")
```

- [ ] **Step 5: Create `icons.json`.** Create `custom_components/patchpilot/icons.json`:

```json
{
  "entity": {
    "sensor": {
      "pending_updates": {
        "default": "mdi:update"
      },
      "installable_updates": {
        "default": "mdi:package-up"
      },
      "skipped_updates": {
        "default": "mdi:update-off"
      },
      "last_run": {
        "default": "mdi:clock-check-outline"
      },
      "last_installed_count": {
        "default": "mdi:package-up"
      },
      "last_failed_count": {
        "range": {
          "0": "mdi:check-circle-outline",
          "1": "mdi:alert-circle-outline"
        }
      },
      "run_history": {
        "default": "mdi:history"
      }
    },
    "binary_sensor": {
      "restart_required": {
        "state": {
          "on": "mdi:restart-alert",
          "off": "mdi:check-circle"
        }
      }
    },
    "switch": {
      "automatic_updates": {
        "default": "mdi:auto-fix"
      }
    },
    "button": {
      "scan_updates": {
        "default": "mdi:refresh"
      },
      "dry_run": {
        "default": "mdi:clipboard-search"
      },
      "run_updates_now": {
        "default": "mdi:play"
      }
    }
  }
}
```

- [ ] **Step 6: Append the `entity` block to `strings.json`.** The current last top-level key is `issues`; add a comma after the `issues` object's closing brace and append the `entity` block. The tail of `strings.json` becomes:

```json
  "issues": {
    "last_run_failed": {
      "title": "PatchPilot failed to install updates",
      "description": "{count} update entity or entities failed during the last update run: {entities}. Check the Home Assistant log for details."
    }
  },
  "entity": {
    "sensor": {
      "pending_updates": {
        "name": "Pending updates"
      },
      "installable_updates": {
        "name": "Installable updates"
      },
      "skipped_updates": {
        "name": "Skipped updates"
      },
      "last_run": {
        "name": "Last run"
      },
      "last_installed_count": {
        "name": "Last installed count"
      },
      "last_failed_count": {
        "name": "Last failed count"
      },
      "run_history": {
        "name": "Run history"
      }
    },
    "binary_sensor": {
      "restart_required": {
        "name": "Restart required"
      }
    },
    "switch": {
      "automatic_updates": {
        "name": "Automatic updates"
      }
    },
    "button": {
      "scan_updates": {
        "name": "Scan updates"
      },
      "dry_run": {
        "name": "Dry run"
      },
      "run_updates_now": {
        "name": "Run updates now"
      }
    }
  }
}
```

- [ ] **Step 7: Regenerate `en.json` byte-identically.**

```bash
cp custom_components/patchpilot/strings.json custom_components/patchpilot/translations/en.json
```

- [ ] **Step 8: Validate JSON for all three files.**

Run:
```bash
python3 -m json.tool custom_components/patchpilot/icons.json > /dev/null
python3 -m json.tool custom_components/patchpilot/strings.json > /dev/null
python3 -m json.tool custom_components/patchpilot/translations/en.json > /dev/null
```
Expected: all valid.

- [ ] **Step 9: Compile-check.**

Run: `python3 -m compileall -q custom_components`
Expected: silent.

- [ ] **Step 10: Run structure tests.**

Run: `pytest tests/test_project_structure.py -q`
Expected: `test_custom_component_translation_is_packaged`, `test_entities_share_patchpilot_device_info`, `test_ui_control_entities_call_manager_actions` pass. `test_integration_forwards_ui_control_platforms` still passes (const.py unchanged here).

- [ ] **Step 11: Commit.**

```bash
git add custom_components/patchpilot/entity.py custom_components/patchpilot/sensor.py custom_components/patchpilot/button.py custom_components/patchpilot/switch.py custom_components/patchpilot/icons.json custom_components/patchpilot/strings.json custom_components/patchpilot/translations/en.json
git commit -m "Move PatchPilot entity names and icons to translations"
```

---

### Task 5: Add the Restart-required binary sensor

**Files:**
- Create: `custom_components/patchpilot/binary_sensor.py`
- Modify: `custom_components/patchpilot/const.py`
- Test: `tests/test_project_structure.py` (edit ONE existing assertion)

**Interfaces:**
- Consumes: `manager.last_result` (`UpdateRunResult | None`), field `restart_required: list[str]`.
- Produces: `binary_sensor` platform with `RestartRequiredBinarySensor(PatchPilotObservableEntity, BinarySensorEntity)`, `translation_key="restart_required"`, `BinarySensorDeviceClass.PROBLEM`. Auto-forwarded once `binary_sensor` is in `PLATFORMS` (no `__init__.py` edit).

- [ ] **Step 1: Make the breaking structural assert fail.** Edit `const.py` line 8:

```python
PLATFORMS = ["binary_sensor", "button", "sensor", "switch"]
```

- [ ] **Step 2: Run and EXPECT FAILURE.**

Run: `pytest tests/test_project_structure.py::test_integration_forwards_ui_control_platforms -q`
Expected: FAIL on `assert 'PLATFORMS = ["button", "sensor", "switch"]' in const_source`.

- [ ] **Step 3: Update the assertion.** In `tests/test_project_structure.py` line 104, change:

```python
    assert 'PLATFORMS = ["button", "sensor", "switch"]' in const_source
```
to:
```python
    assert 'PLATFORMS = ["binary_sensor", "button", "sensor", "switch"]' in const_source
```

- [ ] **Step 4: Re-run and EXPECT PASS.**

Run: `pytest tests/test_project_structure.py::test_integration_forwards_ui_control_platforms -q`
Expected: 1 passed.

- [ ] **Step 5: Create `binary_sensor.py`.** Create `custom_components/patchpilot/binary_sensor.py`:

```python
"""Binary sensors for PatchPilot."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up PatchPilot binary sensors."""
    manager = hass.data[DOMAIN][DATA_MANAGERS][entry.entry_id]
    async_add_entities([RestartRequiredBinarySensor(manager)])


class RestartRequiredBinarySensor(PatchPilotObservableEntity, BinarySensorEntity):
    """Report when the last run needs a Home Assistant restart."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, manager: PatchPilotManager) -> None:
        """Initialize binary sensor."""
        super().__init__(manager, "restart_required")

    @property
    def is_on(self) -> bool:
        """Return true when the last run requires a restart."""
        return bool(
            self.manager.last_result and self.manager.last_result.restart_required
        )
```

- [ ] **Step 6: Compile-check.**

Run: `python3 -m compileall -q custom_components`
Expected: silent.

- [ ] **Step 7: Validate icons.json still parses** (it already contains `binary_sensor.restart_required` from Task 4).

Run: `python3 -m json.tool custom_components/patchpilot/icons.json > /dev/null && echo OK`
Expected: `OK`.

- [ ] **Step 8: Run the full structural suite.**

Run: `pytest tests/test_project_structure.py -q`
Expected: all pass.

- [ ] **Step 9: Commit.**

```bash
git add custom_components/patchpilot/binary_sensor.py custom_components/patchpilot/const.py tests/test_project_structure.py
git commit -m "Add PatchPilot restart-required binary sensor"
```

---

### Task 6: Manager uses friendly names + presentation builders + direct async_create

**Files:**
- Modify: `custom_components/patchpilot/manager.py`
- Test: `tests/test_project_structure.py` (relocate two existing assertions)

**Interfaces:**
- Consumes (Task 2): `from .presentation import (build_failure_notification, build_restart_required_notification, build_skipped_updates_notification, build_updates_installed_notification)`.
- Consumes (HA): `from homeassistant.components.persistent_notification import async_create, async_dismiss` — `async_create(hass, message, title=None, notification_id=None)` is a `@callback` (synchronous, NOT awaited); `async_dismiss(hass, notification_id)`. `hass.states.get(entity_id).name` → friendly name; `None` when entity missing.
- Produces (unchanged): same notification ids — failure `f"{DOMAIN}_{entry_id}_last_run_failed"`, restart/installed share `f"{DOMAIN}_{entry_id}_restart_required"`, skipped `f"{DOMAIN}_{entry_id}_skipped_updates"`. Preserves method names `_async_notify_failure`, `_async_notify_restart_required`, `_async_notify_updates_installed`, `_async_notify_skipped_updates`, `_async_clear_skipped_updates_notification`, `_async_update_notifications`, `_async_refresh_after_run`.

- [ ] **Step 1: Add imports to `manager.py`.** After line 12 (`from homeassistant.components.update import UpdateEntityFeature`) add:

```python
from homeassistant.components.persistent_notification import (
    async_create as async_create_notification,
    async_dismiss as async_dismiss_notification,
)
```

After the `.update_logic` import block (lines 50-57) add:

```python
from .presentation import (
    build_failure_notification,
    build_restart_required_notification,
    build_skipped_updates_notification,
    build_updates_installed_notification,
)
```

- [ ] **Step 2: Add the `_entity_names` helper.** Insert into `PatchPilotManager` directly after `_home_assistant_restart_required_entities`, before `_finish`:

```python
    def _entity_names(self, *entity_id_groups: Iterable[str]) -> dict[str, str]:
        """Map entity ids to friendly names, falling back to the id itself."""
        names: dict[str, str] = {}
        for group in entity_id_groups:
            for entity_id in group:
                if entity_id in names:
                    continue
                state = self.hass.states.get(entity_id)
                names[entity_id] = state.name if state is not None else entity_id
        return names
```

- [ ] **Step 3: Refactor `_async_notify_failure`.** Replace the method body (lines 482-502) with:

```python
    async def _async_notify_failure(self, result: UpdateRunResult) -> None:
        """Create a persistent notification after failed installs."""
        if not self.options.get(CONF_NOTIFY_ON_FAILURE, DEFAULT_NOTIFY_ON_FAILURE):
            return
        names = self._entity_names(result.failed)
        title, message = build_failure_notification(result.failed, names)
        async_create_notification(
            self.hass,
            message,
            title=title,
            notification_id=f"{DOMAIN}_{self.entry.entry_id}_last_run_failed",
        )
```

- [ ] **Step 4: Refactor `_async_notify_restart_required`.** Replace the method (lines 539-570) with:

```python
    async def _async_notify_restart_required(self, result: UpdateRunResult) -> None:
        """Create a persistent notification requesting a Home Assistant restart."""
        names = self._entity_names(
            result.installed,
            result.restart_required,
            result.filtered,
            result.uninstallable,
        )
        title, message = build_restart_required_notification(
            result.installed,
            result.restart_required,
            result.filtered,
            result.uninstallable,
            names,
        )
        async_create_notification(
            self.hass,
            message,
            title=title,
            notification_id=f"{DOMAIN}_{self.entry.entry_id}_restart_required",
        )
```

- [ ] **Step 5: Refactor `_async_notify_updates_installed`.** Replace the method (lines 572-600) with:

```python
    async def _async_notify_updates_installed(self, result: UpdateRunResult) -> None:
        """Create a persistent notification after non-HA-runtime updates install."""
        names = self._entity_names(
            result.installed, result.filtered, result.uninstallable
        )
        title, message = build_updates_installed_notification(
            result.installed,
            result.filtered,
            result.uninstallable,
            names,
        )
        async_create_notification(
            self.hass,
            message,
            title=title,
            notification_id=f"{DOMAIN}_{self.entry.entry_id}_restart_required",
        )
```

- [ ] **Step 6: Refactor `_async_notify_skipped_updates`.** Replace the method (lines 504-522) with:

```python
    async def _async_notify_skipped_updates(self, result: UpdateRunResult) -> None:
        """Create a persistent notification listing skipped pending updates."""
        names = self._entity_names(result.filtered, result.uninstallable)
        title, message = build_skipped_updates_notification(
            result.filtered, result.uninstallable, names
        )
        async_create_notification(
            self.hass,
            message,
            title=title,
            notification_id=f"{DOMAIN}_{self.entry.entry_id}_skipped_updates",
        )
```

- [ ] **Step 7: Refactor `_async_clear_skipped_updates_notification`.** Replace the method (lines 524-537) with:

```python
    async def _async_clear_skipped_updates_notification(self) -> None:
        """Dismiss the skipped-updates notification when no updates are skipped."""
        async_dismiss_notification(
            self.hass,
            f"{DOMAIN}_{self.entry.entry_id}_skipped_updates",
        )
```

- [ ] **Step 8: Remove dead helpers and constants.** Delete the module-level `_format_entity_list` (lines 648-650) and `_format_skipped_update_sections` (lines 653-666). Delete the now-unused constants `PERSISTENT_NOTIFICATION_DOMAIN`, `PERSISTENT_NOTIFICATION_CREATE`, `PERSISTENT_NOTIFICATION_DISMISS` (lines 65-67).

- [ ] **Step 9: Relocate the moved-literal structural assertions.** In `tests/test_project_structure.py`, edit `test_manager_only_requests_restart_for_ha_runtime_updates`: add a presentation source read and move the two title-literal asserts to it. Replace the function body with:

```python
def test_manager_only_requests_restart_for_ha_runtime_updates() -> None:
    """PatchPilot should not ask for an HA restart after external updates."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()
    update_logic_source = (INTEGRATION_DIR / "update_logic.py").read_text()
    presentation_source = (INTEGRATION_DIR / "presentation.py").read_text()

    assert "requires_home_assistant_restart" in update_logic_source
    assert 'HA_RESTART_UPDATE_PLATFORMS = frozenset({"hacs"})' in update_logic_source
    assert '"update.home_assistant_core_update"' in update_logic_source
    assert "restart_required: list[str]" in manager_source
    assert (
        "result.restart_required = self._home_assistant_restart_required_entities"
        in (manager_source)
    )
    assert "if result.restart_required:" in manager_source
    assert "async def _async_notify_restart_required" in manager_source
    assert "await self._async_notify_restart_required(result)" in manager_source
    assert "await self._async_notify_updates_installed(result)" in manager_source
    assert "entity_registry.async_get(self.hass)" in manager_source
    assert '"restart_required": result.restart_required' in manager_source
    # Notification title text moved to presentation.py.
    assert '"PatchPilot restart required"' in presentation_source
    assert '"PatchPilot updates installed"' in presentation_source
    assert "_restart_required" in manager_source
```

Then edit `test_manager_lists_skipped_updates_after_runs`: move the two label literals to presentation. Replace its body with:

```python
def test_manager_lists_skipped_updates_after_runs() -> None:
    """PatchPilot should list skipped pending updates and why they were skipped."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()
    sensor_source = (INTEGRATION_DIR / "sensor.py").read_text()
    presentation_source = (INTEGRATION_DIR / "presentation.py").read_text()

    assert "filtered: list[str]" in manager_source
    assert "uninstallable: list[str]" in manager_source
    assert "result.filtered = [" in manager_source
    assert "result.uninstallable = [" in manager_source
    assert "await self._async_notify_skipped_updates(result)" in manager_source
    assert "async def _async_notify_skipped_updates" in manager_source
    # Skipped-section labels moved to presentation.py.
    assert "Filtered by PatchPilot configuration" in presentation_source
    assert "Pending but not installable through Home Assistant" in presentation_source
    assert "await self._async_clear_skipped_updates_notification()" in manager_source
    assert '"skipped": result.filtered + result.uninstallable' in manager_source
    assert '"filtered": result.filtered' in manager_source
    assert '"uninstallable": result.uninstallable' in manager_source
    assert '"skipped": result.filtered + result.uninstallable' in sensor_source
```

- [ ] **Step 10: Compile, verify cleanup, run tests.**

Run:
```bash
python3 -m compileall -q custom_components
grep -n "_format_skipped_update_sections\|PERSISTENT_NOTIFICATION_CREATE\|PERSISTENT_NOTIFICATION_DISMISS" custom_components/patchpilot/manager.py || echo "clean"
pytest tests/test_project_structure.py tests/test_presentation.py -q
```
Expected: compile silent; grep prints `clean`; tests pass.

- [ ] **Step 11: Commit.**

```bash
git add custom_components/patchpilot/manager.py tests/test_project_structure.py
git commit -m "Build notifications from friendly names via presentation"
```

---

### Task 7: Manager retry entry point and fixable failure issue

**Files:**
- Modify: `custom_components/patchpilot/manager.py`

**Interfaces:**
- Consumes (Task 1): `from .update_logic import select_retry_entities` — `select_retry_entities(failed: dict[str, str] | None) -> list[str]`.
- Produces (consumed by Task 8): `async def async_retry_failed(self) -> UpdateRunResult`; the `last_run_failed` issue now carries `is_fixable=True` and `data={"entry_id": self.entry.entry_id}`.

- [ ] **Step 1: Add `select_retry_entities` to the update_logic import.** Replace the import block (lines 50-57) with:

```python
from .update_logic import (
    UpdateCandidate,
    UpdateSelectionSummary,
    is_time_in_window,
    parse_time,
    requires_home_assistant_restart,
    select_retry_entities,
    summarize_update_candidates,
)
```

- [ ] **Step 2: Make the failure issue fixable.** In `_create_failure_issue` (lines 466-480), change `is_fixable=False` to `is_fixable=True` and add `data={"entry_id": self.entry.entry_id}`:

```python
    def _create_failure_issue(self, result: UpdateRunResult) -> None:
        """Create or update a repair issue after failed installs."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._failure_issue_id,
            is_fixable=True,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="last_run_failed",
            translation_placeholders={
                "count": str(len(result.failed)),
                "entities": ", ".join(sorted(result.failed)),
            },
            data={"entry_id": self.entry.entry_id},
        )
```

- [ ] **Step 3: Add `async_retry_failed`.** Insert as a public method directly after `async_run` (after line 262):

```python
    async def async_retry_failed(self) -> UpdateRunResult:
        """Re-run the most recently failed update entities, ignoring the window."""
        last_result = self.last_result
        failed = last_result.failed if last_result is not None else None
        retry_ids = select_retry_entities(failed)
        if not retry_ids:
            now = dt_util.utcnow()
            return UpdateRunResult(
                reason="repair_retry",
                started_at=now,
                finished_at=now,
                skipped_reason="nothing_to_retry",
            )
        return await self.async_run(
            reason="repair_retry",
            entity_ids=retry_ids,
            ignore_window=True,
        )
```

(The no-op branch returns a fresh result without calling `_finish`, so `last_result`/history/listeners are untouched when there is nothing to retry.)

- [ ] **Step 4: Add a structural assertion for the retry path.** Append to `tests/test_project_structure.py`:

```python
def test_manager_exposes_repair_retry_entry_point() -> None:
    """The manager should offer a retry path and a fixable failure issue."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()

    assert "async def async_retry_failed" in manager_source
    assert 'reason="repair_retry"' in manager_source
    assert "select_retry_entities" in manager_source
    assert "is_fixable=True" in manager_source
    assert 'data={"entry_id": self.entry.entry_id}' in manager_source
```

- [ ] **Step 5: Compile and run tests.**

Run:
```bash
python3 -m compileall -q custom_components
pytest tests/test_project_structure.py -q -k repair_retry_entry_point
pytest tests/test_update_logic.py -q
```
Expected: compile silent; both test runs pass.

- [ ] **Step 6: Commit.**

```bash
git add custom_components/patchpilot/manager.py tests/test_project_structure.py
git commit -m "Add repair-driven retry and fixable failure issue"
```

---

### Task 8: Fixable Repairs flow for failed runs (retry or dismiss)

> **Shared-file note:** THIRD task editing `strings.json`/`en.json` — replaces the `issues.last_run_failed` block with the fixable `fix_flow` form. After Task 4 appended `entity`, `issues` is NOT the last top-level key, so it is followed by a comma then `entity`. Preserve that.

**Files:**
- Create: `custom_components/patchpilot/repairs.py`
- Modify: `custom_components/patchpilot/strings.json`, `custom_components/patchpilot/translations/en.json`
- Test: `tests/test_project_structure.py` (add ONE new function)

**Interfaces:**
- Consumes (Task 7): the fixable issue with `data={"entry_id": ...}`; `manager.async_retry_failed()`; `DATA_MANAGERS`, `DOMAIN` from `const.py`; manager lookup `hass.data[DOMAIN][DATA_MANAGERS][entry_id]`.
- Produces: module-level `async_create_fix_flow(hass, issue_id, data) -> RepairsFlow` + `PatchPilotFailedRunRepairFlow(RepairsFlow)` with `async_step_init` (menu) / `async_step_retry` / `async_step_dismiss`.
- **Resilience:** missing `entry_id`, missing manager (`KeyError`), or a raising `async_retry_failed` must still complete via `async_create_entry` (which resolves/removes the issue) rather than raising.

> **Verified schema:** `self.async_show_menu(step_id="init", menu_options=["retry", "dismiss"])` resolves option labels from `issues.<key>.fix_flow.step.init.menu_options` (object keyed by option id → label). Terminal steps that call `async_create_entry` without showing a form need no own `fix_flow.step.<id>` entry — only `step.init` (description + menu_options) is required.

- [ ] **Step 1: Write the failing structural test.** Append to `tests/test_project_structure.py`:

```python
def test_failed_run_repair_offers_fixable_menu() -> None:
    """The failed-run repair issue should expose a fixable retry/dismiss flow."""
    repairs_path = INTEGRATION_DIR / "repairs.py"
    assert repairs_path.is_file()

    repairs_source = repairs_path.read_text()
    assert "async def async_create_fix_flow" in repairs_source
    assert "RepairsFlow" in repairs_source
    assert "async_show_menu" in repairs_source
    assert "async_retry_failed" in repairs_source

    strings = json.loads((INTEGRATION_DIR / "strings.json").read_text())
    last_run_failed = strings["issues"]["last_run_failed"]
    assert "fix_flow" in last_run_failed
    assert "description" not in last_run_failed
    menu_options = last_run_failed["fix_flow"]["step"]["init"]["menu_options"]
    assert set(menu_options) == {"retry", "dismiss"}
```

- [ ] **Step 2: Run and EXPECT FAIL.**

Run: `pytest tests/test_project_structure.py::test_failed_run_repair_offers_fixable_menu -q`
Expected: FAIL on `repairs_path.is_file()`.

- [ ] **Step 3: Create `repairs.py`.** Create `custom_components/patchpilot/repairs.py`:

```python
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
```

- [ ] **Step 4: Replace the `issues` block in `strings.json`.** Replace the current `issues` object (the `last_run_failed` with top-level `title` + `description`) with the fixable form below. Keep the trailing comma after the `issues` object's closing brace (because `entity` follows it from Task 4):

```json
  "issues": {
    "last_run_failed": {
      "title": "PatchPilot failed to install updates",
      "fix_flow": {
        "step": {
          "init": {
            "title": "PatchPilot failed to install updates",
            "description": "PatchPilot's last update run failed for {count} update entity or entities: {entities}. Retry these updates now, or dismiss this issue and check the Home Assistant log for details.",
            "menu_options": {
              "retry": "Retry failed updates now",
              "dismiss": "Dismiss"
            }
          }
        }
      }
    }
  },
```

- [ ] **Step 5: Regenerate `en.json` byte-identically.**

```bash
cp custom_components/patchpilot/strings.json custom_components/patchpilot/translations/en.json
```

- [ ] **Step 6: Compile + JSON + byte-identity checks.**

Run:
```bash
python3 -m compileall -q custom_components
python3 -c "import json; json.load(open('custom_components/patchpilot/strings.json')); json.load(open('custom_components/patchpilot/translations/en.json')); print('json ok')"
cmp custom_components/patchpilot/strings.json custom_components/patchpilot/translations/en.json && echo "byte-identical"
```
Expected: silent compile; `json ok`; `byte-identical`.

- [ ] **Step 7: Run the structure suite (deep-equality must stay green).**

Run: `pytest tests/test_project_structure.py -q`
Expected: all pass, including the new `test_failed_run_repair_offers_fixable_menu` and `test_custom_component_translation_is_packaged`.

- [ ] **Step 8: Commit.**

```bash
git add custom_components/patchpilot/repairs.py custom_components/patchpilot/strings.json custom_components/patchpilot/translations/en.json tests/test_project_structure.py
git commit -m "Add fixable repair flow for failed runs"
```

---

### Task 9: Bump version to 0.4.0

**Files:**
- Modify: `custom_components/patchpilot/manifest.json`, `pyproject.toml`, `CHANGELOG.md`, `tests/test_project_structure.py`

**Interfaces:** N/A. The CHANGELOG entry describes Tasks 3–8, so it runs after them.

- [ ] **Step 1: Bump the manifest version.** In `custom_components/patchpilot/manifest.json` change `"version": "0.3.8"` (line 13) to:

```json
  "version": "0.4.0"
```

- [ ] **Step 2: Bump the project version.** In `pyproject.toml` line 3:

```toml
version = "0.4.0"
```

- [ ] **Step 3: Bump the test constant.** In `tests/test_project_structure.py` line 12:

```python
EXPECTED_VERSION = "0.4.0"
```

- [ ] **Step 4: Prepend the CHANGELOG entry.** In `CHANGELOG.md`, insert immediately after the `# Changelog` heading and its blank line, directly above `## 0.3.8 - 2026-06-20`:

```markdown
## 0.4.0 - 2026-06-21

- Split the configuration flow into grouped sections and use Home Assistant
  time selectors for the maintenance-window start and end times.
- Add a `translation_key` to every entity, package an `icons.json` so each
  entity shows a Material Design icon, and add a `Restart required` binary
  sensor that reports when an installed update needs a Home Assistant restart.
- Render friendly entity names in PatchPilot notifications by resolving entity
  display names through a shared `presentation` helper.
- Make the failed-install repair issue fixable with a repair flow that retries
  the failed updates or dismisses the issue.
- Document a ready-to-paste Lovelace dashboard and the new restart-required
  binary sensor in the README.

```

- [ ] **Step 5: Verify the version test passes.**

Run: `pytest tests/test_project_structure.py::test_version_metadata_is_consistent -q`
Expected: 1 passed.

- [ ] **Step 6: Confirm no stray `0.3.8` in the pinned code locations.**

Run: `grep -rn "0\.3\.8" custom_components/patchpilot/manifest.json pyproject.toml tests/test_project_structure.py`
Expected: no matches (exit 1). (The historical `## 0.3.8` CHANGELOG entry legitimately remains — not in this grep.)

- [ ] **Step 7: Commit.**

```bash
git add custom_components/patchpilot/manifest.json pyproject.toml CHANGELOG.md tests/test_project_structure.py
git commit -m "Bump version to 0.4.0"
```

---

### Task 10: Structural tests for new files and icons.json

**Files:**
- Modify: `tests/test_project_structure.py` (extend the expected-files tuple; add one new function)

**Interfaces:** N/A (test-only). Consumes `presentation.py`, `binary_sensor.py`, `repairs.py`, `icons.json`, and the `entity` block in `strings.json`. The icons cross-check compares the set of `(platform, key)` pairs under `icons.json["entity"]` against `strings.json["entity"]` (key presence only — so `range`/`state` keys match).

- [ ] **Step 1: Extend the expected-files tuple.** In `test_repository_has_standard_integration_files`, replace the tuple tail (lines 50-53):

```python
        "custom_components/__init__.py",
        "custom_components/patchpilot/button.py",
        "custom_components/patchpilot/entity.py",
        "custom_components/patchpilot/switch.py",
        "custom_components/patchpilot/translations/en.json",
    )
```
with:
```python
        "custom_components/__init__.py",
        "custom_components/patchpilot/binary_sensor.py",
        "custom_components/patchpilot/button.py",
        "custom_components/patchpilot/entity.py",
        "custom_components/patchpilot/icons.json",
        "custom_components/patchpilot/presentation.py",
        "custom_components/patchpilot/repairs.py",
        "custom_components/patchpilot/switch.py",
        "custom_components/patchpilot/translations/en.json",
    )
```

- [ ] **Step 2: Add the icons cross-check test.** Append to the end of `tests/test_project_structure.py`:

```python
def test_icons_json_is_valid_and_matches_entity_translation_keys() -> None:
    """icons.json entity keys must mirror the strings.json entity keys."""
    icons = json.loads((INTEGRATION_DIR / "icons.json").read_text())
    strings = json.loads((INTEGRATION_DIR / "strings.json").read_text())

    assert isinstance(icons, dict)
    assert isinstance(icons.get("entity"), dict)
    assert isinstance(strings.get("entity"), dict)

    def _platform_key_pairs(entity_block: dict) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for platform, keys in entity_block.items():
            assert isinstance(keys, dict), platform
            for key in keys:
                pairs.add((platform, key))
        return pairs

    icon_pairs = _platform_key_pairs(icons["entity"])
    strings_pairs = _platform_key_pairs(strings["entity"])

    assert icon_pairs, "icons.json defines no entity icons"
    assert icon_pairs == strings_pairs, {
        "missing_name_in_strings": sorted(icon_pairs - strings_pairs),
        "missing_icon_in_icons": sorted(strings_pairs - icon_pairs),
    }
```

- [ ] **Step 3: Run the structure module.**

Run: `pytest tests/test_project_structure.py -q`
Expected: all pass. If the icons test fails with a dict diff, `icons.json` and the `entity` block are genuinely out of sync (a real defect in Task 4) — fix the source, do not relax the assertion.

- [ ] **Step 4: Confirm the new test ran (guard against silent skip).**

Run: `pytest tests/test_project_structure.py -q -k icons_json_is_valid`
Expected: `1 passed`.

- [ ] **Step 5: Commit.**

```bash
git add tests/test_project_structure.py
git commit -m "Add structural tests for new modules"
```

---

### Task 11: Document dashboard and restart sensor in README

**Files:**
- Modify: `README.md`, `info.md`

**Interfaces:** N/A. Consumes the entity IDs produced by Tasks 4–5. Entity IDs follow the `patchpilot_*` convention; the section includes a caveat to confirm exact `entity_id`s in Developer Tools > States.

- [ ] **Step 1: Document the restart binary sensor in the Status list.** In `README.md`, insert a bullet immediately before the `- `Run history`` bullet so it reads:

```markdown
- `Last run`: the latest run result, including considered, installed, failed,
  skipped, restart-required, and post-run scan failure details.
- `Restart required`: a binary sensor that is on when the most recent run
  installed an update that needs a Home Assistant restart, such as a
  HACS-managed update or Home Assistant Core.
- `Run history`: compact retained run results.
```

- [ ] **Step 2: Add the Dashboard section.** In `README.md`, insert between `## Status` and `## Services`:

````markdown
## Dashboard

PatchPilot works with a Lovelace dashboard built from Home Assistant's built-in
cards. The YAML below uses the default `patchpilot_*` entity IDs.

> **Confirm your entity IDs first.** Because PatchPilot uses `has_entity_name`,
> Home Assistant composes each entity ID from the device name and the entity
> name, so your slugs may differ (for example if you renamed the device). Open
> **Developer Tools > States**, filter for `patchpilot`, and replace the IDs in
> the YAML with the ones you see there.

Add a manual dashboard card (**Edit dashboard > Add card > Manual**) and paste
each block, or combine them under a single vertical stack.

### Status entities

```yaml
type: entities
title: PatchPilot
entities:
  - entity: sensor.patchpilot_pending_updates
  - entity: sensor.patchpilot_installable_updates
  - entity: sensor.patchpilot_skipped_updates
  - entity: binary_sensor.patchpilot_restart_required
  - entity: sensor.patchpilot_last_run
  - entity: switch.patchpilot_automatic_updates
```

### Last-run summary

```yaml
type: markdown
title: PatchPilot last run
content: >
  **Reason:** {{ state_attr('sensor.patchpilot_last_run', 'reason') }}
  {% if state_attr('sensor.patchpilot_last_run', 'dry_run') %}(dry run){% endif %}

  - Considered: {{ state_attr('sensor.patchpilot_last_run', 'considered') | length }}
  - Installed: {{ state_attr('sensor.patchpilot_last_run', 'installed') | length }}
  - Failed: {{ state_attr('sensor.patchpilot_last_run', 'failed') | length }}
  - Skipped: {{ state_attr('sensor.patchpilot_last_run', 'skipped') | length }}
  - Filtered: {{ state_attr('sensor.patchpilot_last_run', 'filtered') | length }}
  - Uninstallable: {{ state_attr('sensor.patchpilot_last_run', 'uninstallable') | length }}

  {% set restart = state_attr('sensor.patchpilot_last_run', 'restart_required') %}
  {% if restart %}**Restart required for:** {{ restart | join(', ') }}{% else %}No restart required.{% endif %}

  {% set scan_failed = state_attr('sensor.patchpilot_last_run', 'scan_failed') %}
  {% if scan_failed %}**Post-run scan failed:** {{ scan_failed }}{% endif %}
```

### Controls

```yaml
type: horizontal-stack
cards:
  - type: button
    name: Scan updates
    icon: mdi:magnify
    tap_action:
      action: toggle
    entity: button.patchpilot_scan_updates
  - type: button
    name: Dry run
    icon: mdi:clipboard-text-search
    tap_action:
      action: toggle
    entity: button.patchpilot_dry_run
  - type: button
    name: Run updates now
    icon: mdi:download
    tap_action:
      action: toggle
    entity: button.patchpilot_run_updates_now
```
````

- [ ] **Step 3: Add the info.md pointer.** Append to `info.md` after the final sensors paragraph:

```markdown

A `Restart required` binary sensor flags when an installed update needs a Home
Assistant restart. See the README for a ready-to-paste Lovelace dashboard built
from Home Assistant's built-in cards.
```

- [ ] **Step 4: Review the rendered diff.**

Run: `git diff -- README.md info.md`
Confirm: `## Dashboard` sits between `## Status` and `## Services`; fenced blocks balanced; restart bullet present; `info.md` pointer added.

- [ ] **Step 5: Confirm the suite still passes.**

Run: `pytest -q`
Expected: full suite passes.

- [ ] **Step 6: Commit.**

```bash
git add README.md info.md
git commit -m "Document PatchPilot dashboard"
```

---

### Task 12: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire test suite.**

Run: `pytest -q`
Expected: all pass — confirms version bump, expanded expected-files tuple, icons cross-check, presentation builders, and pure helpers all green together.

- [ ] **Step 2: Run pre-commit across the tree.**

Run: `pre-commit run --all-files`
Expected: every hook `Passed` or `Skipped`; none `Failed`. If black/isort reauthor files, re-stage and re-run until clean, then amend the relevant commit or add a `Apply pre-commit formatting` commit.

- [ ] **Step 3: Sanity-check the working tree is clean.**

Run: `git status --short`
Expected: empty (all work committed).

- [ ] **Step 4: Confirm the integration imports as a module graph (compile-all).**

Run: `python3 -m compileall -q custom_components tests`
Expected: silent (exit 0).
