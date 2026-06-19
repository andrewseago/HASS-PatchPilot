# Home Assistant Tooling Notes

Verified: 2026-06-19

## Repository

- Path: `/Users/andrewws/GitHub/HASS-PatchPilot`
- Git branch: `master`
- GitHub remote: `https://github.com/andrewseago/HASS-PatchPilot.git`
- Integration domain: `auto_update_manager`
- Integration path: `custom_components/auto_update_manager`

## Local Checks

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
pytest -q
python3 -m compileall -q custom_components tests
python3 -m json.tool custom_components/auto_update_manager/manifest.json >/tmp/patchpilot_manifest_check.json
python3 -m json.tool custom_components/auto_update_manager/strings.json >/tmp/patchpilot_strings_check.json
python3 -c 'import yaml, pathlib; yaml.safe_load(pathlib.Path("custom_components/auto_update_manager/services.yaml").read_text())'
```

`ruff` is not currently on PATH in this shell.

## Home Assistant Custom Integration Notes

- Custom integrations must include `version` in `manifest.json`.
- `config_flow: true` requires `config_flow.py`.
- HACS requires repository-root `hacs.json`, a README, one integration under
  `custom_components/`, manifest metadata, and brand assets.
- Current Home Assistant custom integration brand assets can live under
  `custom_components/<domain>/brand/`.

## Current Test Coverage

The local tests cover the pure update-selection helpers in
`custom_components/auto_update_manager/update_logic.py`.

Runtime tests against a Home Assistant test harness are not present yet.
