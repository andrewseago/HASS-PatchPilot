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
