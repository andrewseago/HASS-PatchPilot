# PatchPilot Usability & UI Improvements — Design

**Date:** 2026-06-21
**Status:** Approved (brainstorming complete; ready for implementation planning)
**Target:** Home Assistant 2026.6.0 (the integration's declared minimum, per `hacs.json`)
**Version bump:** 0.3.8 → 0.4.0 (new features, backward-compatible)

## Summary

A coordinated usability and UI pass across four surfaces of the PatchPilot
custom integration — config/options flow, entities, notifications, and repairs —
plus documented dashboard guidance. Every change is additive and reversible,
keeps the repository pure-Python (no frontend build), and respects the existing
architecture: testable logic lives in stdlib-only helper modules, HA glue stays
thin.

This is **Approach A** of three considered. Approach B (skip the repair fix-flow
and the new binary_sensor) was rejected for leaving the two "buried" UX problems
unsolved. Approach C (refactor to `DataUpdateCoordinator`, richer entity set) was
rejected because it rewrites a working core for no user-visible gain — and
research confirmed the current hand-rolled listener model is *not* a documented
HA anti-pattern, only the less-batteries-included path.

## Goals

- Make first-time setup understandable: grouped fields, native time pickers,
  inline help for non-obvious options.
- Modernize entities to HA's translation-key + `icons.json` system, including
  state-based icons, and surface "restart required" as a glanceable entity.
- Make notifications human-readable (friendly names) and move their text into
  unit-tested pure builders.
- Turn a failed run into a one-click recovery via a fixable Repairs flow.
- Give users a ready-to-paste dashboard without adding any tooling.

## Non-Goals

- **No `DataUpdateCoordinator` refactor.** The hand-rolled listener/notify model
  stays. (Verified: not a documented anti-pattern.)
- **No custom JavaScript/Lovelace card.** Dashboard guidance is documented YAML
  using built-in cards only.
- **No change to update-selection behavior.** `summarize_update_candidates` and
  the install/window/debounce logic keep their current semantics. This is a
  presentation and configuration-UX pass, not a behavior change.

## Architecture & Guiding Principles

PatchPilot's one structural rule: testable logic lives in pure, stdlib-only
helpers (`update_logic.py`), and HA-coupled glue stays thin. This design extends
that rather than working against it.

- **New pure helper module `presentation.py`** (stdlib only, unit-tested) holds
  all notification message construction and friendly-name-aware formatting.
  Today those f-strings are embedded in `manager.py`'s async methods where they
  cannot be unit-tested. The manager resolves `entity_id → friendly name` (an HA
  call) and passes a plain `dict[str, str]` map plus the run result into the pure
  builders, which return `(title, message)` strings.
- **Additive & reversible:** new files (`presentation.py`, `binary_sensor.py`,
  `repairs.py`, `icons.json`) and one new entity, rather than rewrites. Config
  flow and string changes are declarative.
- **Two-file string discipline:** `strings.json` and `translations/en.json` are
  byte-identical today and must stay so — custom integrations load
  `translations/en.json` at runtime (`strings.json` is not build-processed for
  custom integrations). A structural test will assert equality so future drift
  fails CI.

### File inventory

**New files:**

- `custom_components/patchpilot/presentation.py` — pure notification/message builders.
- `custom_components/patchpilot/binary_sensor.py` — "Restart required" entity.
- `custom_components/patchpilot/repairs.py` — `async_create_fix_flow` + retry/dismiss `RepairsFlow`.
- `custom_components/patchpilot/icons.json` — translation-key-based entity icons.
- `tests/test_presentation.py` — unit tests for the message builders.

**Modified files:**

- `config_flow.py` — sectioned schema, `TimeSelector`, `data_description` help.
- `update_logic.py` — add `flatten_sectioned_input` and `select_retry_entities` pure helpers.
- `manager.py` — friendly-name resolution; delegate message text to `presentation.py`;
  switch to direct `persistent_notification.async_create`/`async_dismiss`; make the
  failure issue `is_fixable=True`; expose a retry entry point for the repair flow.
- `sensor.py`, `button.py`, `switch.py`, `entity.py` — add `translation_key`, drop
  `_attr_icon`/`_attr_name` in favor of translations + `icons.json`.
- `const.py` — add `PLATFORMS` entry for `binary_sensor`; any new constants.
- `strings.json` + `translations/en.json` — sections, `data_description`, `entity`
  block, repair `fix_flow` strings; kept identical.
- `tests/test_project_structure.py` — version bump, expected-files/platforms list,
  `strings.json == en.json` assertion, `icons.json` validity + key-match assertions.
- `tests/test_update_logic.py` — tests for the two new pure helpers.
- `README.md`, `info.md` — dashboard YAML + restart-sensor docs.
- `CHANGELOG.md`, `manifest.json`, `pyproject.toml` — version 0.4.0.

## Detailed Design

### 1. Config & options flow

Group the 12 fields into four collapsible `section`s
(`from homeassistant.data_entry_flow import section`, HA 2024.7+):

| Section | Fields | Initial state |
|---|---|---|
| **Schedule** | enabled, check_interval_minutes, window_start, window_end | expanded |
| **What to update** | include_patterns, exclude_patterns, excluded_entities | expanded |
| **Install behavior** | create_backup, max_updates_per_run | collapsed |
| **Notifications & history** | run_on_state_change, notify_on_failure, log_size | collapsed |

Field-level improvements:

- **window_start / window_end → `TimeSelector`** (native HH:MM:SS picker).
  `TimeSelector` returns a `"HH:MM:SS"` string — the exact format already stored
  and already validated by `parse_time`. **No data migration.** The
  `invalid_time` validation remains as a safety net (and still applies if a value
  arrives from an older entry or import).
- **`data_description` help text** on non-obvious fields:
  - `max_updates_per_run`: "0 means no limit."
  - `log_size`: "0 disables run history."
  - `include_patterns` / `exclude_patterns`: note shell-style globs, e.g.
    `update.*` to match all, `update.router*` to match a prefix.

**Nested-input handling (the gotcha):** sectioned forms return values nested
under the section key (`user_input["schedule"]["window_start"]`). Stored entry
data must stay **flat** for backward compatibility. Therefore:

- A new pure helper `flatten_sectioned_input(user_input, section_map)` in
  `update_logic.py` flattens the nested dict back to the flat shape that
  `_validate_input` / `_normalize_input` already expect. Unit-tested.
- The schema builder maps each flat stored value back into its section's defaults
  when rendering the form (re-using the existing `values.get(...)` default
  pattern, just nested).

**Backward compatibility:** existing config entries store flat data and continue
to load unchanged. Only the *form presentation* is sectioned; input is flattened
before validation and save. The options flow reload path (`_async_update_listener`)
is unchanged.

### 2. Entities — names, icons, glanceable restart

**2a. `translation_key` + `icons.json` (HA 2024.2+).**

- Every entity sets `_attr_translation_key` (it already sets
  `_attr_has_entity_name = True` and a `unique_id`, the two prerequisites).
- Entity names move from `_attr_name`/Python into the `entity` block of
  `strings.json` and `translations/en.json`:
  `entity.<platform>.<translation_key>.name`.
- New `icons.json` maps icons by translation key
  (`entity.<platform>.<translation_key>`), replacing the `_attr_icon`
  assignments. This enables **state-based icons** the current code cannot express.

Initial icon mapping (preserving today's icons, adding state variants where useful):

- sensor `pending_updates`: `mdi:update`
- sensor `installable_updates`: `mdi:package-up`
- sensor `skipped_updates`: `mdi:update-off`
- sensor `last_run`: `mdi:clock-check-outline`
- sensor `last_installed_count`: `mdi:package-up`
- sensor `last_failed_count`: range-based — `mdi:check-circle-outline` at 0,
  `mdi:alert-circle-outline` at ≥1
- sensor `run_history`: `mdi:history`
- switch `automatic_updates`: `mdi:auto-fix`
- button `scan_updates`: `mdi:refresh`; `dry_run`: `mdi:clipboard-search`;
  `run_updates_now`: `mdi:play`
- binary_sensor `restart_required` (new): state-based —
  on `mdi:restart-alert`, off `mdi:check-circle`

**2b. New `binary_sensor`: "Restart required"** (`device_class: PROBLEM`).

- `is_on` is driven by `bool(manager.last_result and manager.last_result.restart_required)`.
- Reads existing manager state only — no new core logic. Subscribes to the
  manager via the existing `PatchPilotObservableEntity` base.
- Surfaces "does HA need restarting?" as a glanceable on/off entity (dashboard
  badge, automation trigger) instead of being buried in `last_run` attributes.
- Adds `binary_sensor` to `PLATFORMS`.

### 3. Notifications & Repairs

**3a. Friendly names.** Resolve display names via
`hass.states.get(entity_id).name`, guarded for `None` (falls back to the
entity_id when the entity is not loaded). `State.name` is always a non-empty
string for a loaded entity. Notifications render as
`Home Assistant Core (`update.home_assistant_core_update`)` — friendly name for
humans, entity_id in code formatting for precision.

**3b. Testable message bodies.** All notification title/message construction moves
to pure builders in `presentation.py`. The manager:

1. Builds a `dict[str, str]` of `entity_id → display_name` for the entities in the
   run result (the only HA-coupled step).
2. Calls the pure builder (e.g. `build_restart_required_notification(result,
   names)`) which returns `(title, message)`.
3. Calls `persistent_notification.async_create(hass, message, title=...,
   notification_id=...)` — the direct function import (preferred over the service
   call; `hass.components.*` accessors are removed in current HA and must not be
   used). Dismissal uses `async_dismiss`.

The set of notifications and their trigger conditions is unchanged (failure;
restart-required vs installed; skipped-updates create/dismiss) — only their text
construction and name rendering change.

**3c. Failed run → fixable Repairs flow (HA 2022.8+; registry import from
`homeassistant.helpers.issue_registry`).**

- The existing failure issue becomes `is_fixable=True` and carries
  `data={"entry_id": ...}` so the flow can find the manager.
- New `repairs.py` exposes
  `async def async_create_fix_flow(hass, issue_id, data) -> RepairsFlow` returning
  a custom `RepairsFlow` (not `ConfirmRepairFlow`, because we offer a choice).
- The flow's first step presents the two choices via `async_show_menu` (the
  idiomatic HA pattern for branching a flow): **"Retry failed updates now"** or
  **"Dismiss"**. Each menu option routes to its own step.
  - *Retry:* calls a new manager entry point that re-runs the failed entity_ids
    with `ignore_window=True`. The set of entity_ids to retry is computed by a new
    pure helper `select_retry_entities(last_result)` in `update_logic.py`
    (unit-tested). On success the flow calls `async_create_entry(...)`, which
    auto-clears the issue; if the retry itself fails, the issue is re-created by
    the run's normal failure path.
  - *Dismiss:* `async_create_entry(...)` clears the issue without acting.
- This is the only in-app mechanism for an actionable button — persistent
  notifications cannot carry actions.
- Repair strings move to `issues.last_run_failed.fix_flow.step.*` in both string
  files. The current non-fixable `title`/`description` keys are replaced by the
  `fix_flow` structure.

### 4. Dashboard documentation

A ready-to-paste Lovelace YAML block in `README.md` (and a short pointer in
`info.md`), using built-in cards only:

- **Entities card:** pending, installable, skipped, restart-required, last-run.
- **Markdown card:** binds `last_run` attributes (considered / installed / failed
  / skipped / restart_required) into a human-readable summary.
- **Button-card row:** Scan updates / Dry run / Run updates now.

No new tooling, no JS build, no release-pipeline change.

## Testing Strategy

All tests remain pure (no Home Assistant runtime harness), consistent with the
repo's existing approach.

- **`tests/test_presentation.py` (new):** each notification builder — failure,
  restart-required, updates-installed, skipped-updates — including the
  friendly-name map and the entity_id fallback when a name is missing.
- **`tests/test_update_logic.py` (extended):**
  - `flatten_sectioned_input`: nested→flat for all four sections, and a flat
    passthrough (idempotence) case.
  - `select_retry_entities`: returns the failed entity_ids from a result; empty
    when none failed.
- **`tests/test_project_structure.py` (extended):**
  - `EXPECTED_VERSION` → `0.4.0`.
  - `strings.json` and `translations/en.json` parse and are **deep-equal**.
  - `icons.json` exists, is valid JSON, and every `entity.<platform>.<key>`
    corresponds to an entity translation key (and vice versa).
  - Expected-files list includes `presentation.py`, `binary_sensor.py`,
    `repairs.py`, `icons.json`.
  - `PLATFORMS` includes `binary_sensor`.

CI (pre-commit, HACS validation, Hassfest, pytest) must stay green. Hassfest
validates `strings.json`/`icons.json`/`services.yaml` structure, so string and
icon edits must be well-formed.

## Version & Release

- Bump `0.3.8 → 0.4.0` in all four pinned locations: `manifest.json`,
  `pyproject.toml`, `CHANGELOG.md`, and `EXPECTED_VERSION` in
  `tests/test_project_structure.py`.
- Add a `0.4.0` CHANGELOG entry summarizing the four areas.

## Risks & Mitigations

- **Sectioned-input flattening bug** could corrupt saved options. *Mitigation:*
  flattening is a pure, unit-tested helper; stored shape stays flat and identical
  to today.
- **String-file drift** (editing one of `strings.json`/`en.json`, not both) would
  ship raw keys to users. *Mitigation:* deep-equality test fails CI.
- **`icons.json` key mismatch** silently drops icons. *Mitigation:* structural
  test cross-checks icon keys against entity translation keys.
- **Repair retry re-entrancy:** a retry that triggers another failure must not
  loop. *Mitigation:* the flow performs a single run and exits; re-failure simply
  re-raises the standard issue for the user to act on again. The manager's
  existing `asyncio.Lock` serializes runs.
- **Min-version creep:** all features used are ≤ HA 2024.7; the declared minimum
  is 2026.6.0, so there is ample headroom. No `manifest.json` bump needed beyond
  version.

## Verified Facts (research, 2026-06-21)

- Config-flow `section`: `homeassistant.data_entry_flow.section`, strings under a
  step-level `sections` key; **HA 2024.7+**.
- `TimeSelector`: returns `"HH:MM:SS"` string; long-stable.
- `icons.json`: entity icons keyed by `translation_key`; default/state/range
  variants; switch and button supported; **HA 2024.2+**.
- `translation_key` entity names require `has_entity_name=True` + `unique_id`
  (both already present).
- Custom integrations must ship a flat `translations/en.json` (no `[%key:%]`
  refs) — it is the runtime-loaded file.
- Repairs/fix flows: **HA 2022.8+**; issue registry import from
  `homeassistant.helpers.issue_registry`; flow classes from
  `homeassistant.components.repairs`.
- Friendly name: `hass.states.get(entity_id).name`, guard for `None`.
- `persistent_notification.async_create` (direct import) is current and preferred;
  `hass.components.persistent_notification.*` is removed in current HA. Persistent
  notifications cannot carry action buttons — a fixable repair issue is the in-app
  actionable mechanism.
