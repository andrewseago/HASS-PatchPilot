# PatchPilot

![PatchPilot icon](custom_components/patchpilot/brand/icon.png)

PatchPilot is a Home Assistant custom integration that installs selected pending
`update` entities during a maintenance window.

It can manage Home Assistant Core, Home Assistant OS, Supervisor, add-ons, HACS,
and other integrations that expose installable `update` entities.

## Features

- Scans `update.*` entities.
- Installs only pending entities with `UpdateEntityFeature.INSTALL`.
- Requests backups only when the update entity supports backups.
- Limits automatic installation to a configurable maintenance window.
- Supports include and exclude patterns plus exact entity exclusions.
- Provides services for manual runs, dry runs, scans, and exclusion management.
- Creates a repair issue and optional persistent notification when installs fail.
- Requests a Home Assistant restart only for installed updates that affect the
  Home Assistant runtime, such as HACS-managed updates and Home Assistant Core.
- Sends a non-restart completion notification for external device or service
  updates.
- Lists pending updates that PatchPilot will not install, grouped by reason.
- Exposes diagnostic sensors for raw pending updates, installable updates,
  skipped updates, last run, install count, failure count, and retained run
  history.

## Installation

### HACS custom repository

1. In HACS, add `andrewseago/HASS-PatchPilot` as a custom repository.
2. Select repository type `Integration`.
3. Download PatchPilot.
4. Restart Home Assistant.
5. Add PatchPilot from **Settings > Devices & services**.

### Manual install

1. Copy `custom_components/patchpilot` into the Home Assistant
   `custom_components` directory.
2. Restart Home Assistant.
3. Add PatchPilot from **Settings > Devices & services**.

## Home Assistant UI

After configuring PatchPilot from **Settings > Devices & services**, Home
Assistant creates one PatchPilot device under the integration entry. That device
groups the diagnostic sensors with these direct controls:

- `Automatic updates` switch
- `Scan updates` button
- `Dry run` button
- `Run updates now` button

The buttons use the same manager logic as the services below.

## Configuration

Open **Settings > Devices & services > PatchPilot > Configure** to change:

- Automatic updates enabled/disabled.
- Check interval in minutes.
- Maintenance window start and end times.
- Include and exclude entity patterns.
- Exact excluded `update` entities.
- Backup requests when supported by the update entity.
- Maximum updates per run, where `0` means no limit.
- Whether newly pending updates trigger an automatic run during the maintenance
  window.
- Failure notifications.
- Retained run-history size.

PatchPilot stores exact exclusions in the integration options. The
`patchpilot.exclude_entities` and `patchpilot.include_entities` services update
that same setting.

## Status

The integration exposes diagnostic entities on one PatchPilot device:

- `Pending updates`: every pending `update` entity matching the include/exclude
  configuration.
- `Installable updates`: pending entities that expose Home Assistant's install
  feature.
- `Skipped updates`: pending entities PatchPilot will not install, either
  because configuration filtered them or Home Assistant cannot install them.
- `Last run`: the latest run result, including considered, installed, failed,
  skipped, restart-required, and post-run scan failure details.
- `Run history`: compact retained run results.

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

Remove one or more `update` entities from the exclusion list.

## Development

Run the local tests:

```bash
python3 -m unittest discover -s tests -v
pytest -q
```

The current tests cover the pure update-selection helpers and repository
structure. Full Home Assistant runtime tests are not included yet.

## Versioning

PatchPilot uses SemVer. Keep `custom_components/patchpilot/manifest.json`,
`pyproject.toml`, and `CHANGELOG.md` on the same version. GitHub release tags
should use `vX.Y.Z`.
