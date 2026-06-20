# PatchPilot

![PatchPilot icon](./brand/icon.png)

PatchPilot installs pending Home Assistant `update` entities during a maintenance
window. This covers Home Assistant Core, Home Assistant OS, Supervisor, add-ons,
HACS, and any other integration that exposes installable update entities.

## Behavior

- Scans all `update.*` entities.
- Installs only entities with state `on`.
- Installs only entities that advertise `UpdateEntityFeature.INSTALL`.
- Requests a backup only when the entity advertises `UpdateEntityFeature.BACKUP`.
- Runs sequentially, not concurrently.
- Creates a Home Assistant repair issue if any install fails.
- Creates a persistent notification when installs fail, if enabled.
- Provides sensors for raw pending count, installable count, skipped count, last
  run, last installed count, and last failed count.
- Provides a diagnostic run-history sensor with retained run summaries.

## Default options

- Enabled: `true`
- Check interval: `60` minutes
- Maintenance window: `03:00:00` to `05:00:00`
- Include patterns: `update.*`
- Exclude patterns: none
- Excluded update entities: none
- Create backups when supported: `true`
- Max updates per run: `0` (unlimited)
- Run when update entities become pending: `true`
- Notify on failure: `true`
- Run history size: `25`

## UI

The integration uses native Home Assistant UI surfaces:

- Config flow under **Settings > Devices & services**.
- Options flow for maintenance window, include/exclude patterns, backup
  behavior, exact excluded update entities, failure notifications, and
  run-history size.
- Diagnostic sensors for pending updates, installable updates, skipped updates,
  last run, installed count, failed count, and run history.
- Repair issues and persistent notifications for failures.

It does not ship a custom Lovelace panel.

## Services

### `patchpilot.run_updates`

Run an update pass manually.

Optional fields:

- `entity_id`: one or more `update` entities.
- `ignore_window`: run outside the configured maintenance window.
- `dry_run`: select matching pending entities without installing them.

### `patchpilot.scan`

Refresh update entities and the pending-update counter.

### `patchpilot.exclude_entities`

Persistently add one or more `update` entities to the exclusion list.

### `patchpilot.include_entities`

Remove one or more `update` entities from the exclusion list so they can be
updated automatically again.
