# Changelog

## 0.3.2 - 2026-06-20

- Classify PatchPilot as a service integration so it appears with configured
  service integrations in Home Assistant.
- Use Home Assistant's `single_config_entry` manifest guard to prevent duplicate
  PatchPilot config entries from repeated setup attempts.

## 0.3.1 - 2026-06-20

- Allow creating a fresh PatchPilot config entry when Home Assistant has a stale
  hidden entry that would otherwise trigger `already_configured`.

## 0.3.0 - 2026-06-20

- Add native PatchPilot UI entities under one integration device.
- Add Scan updates, Dry run, and Run updates now buttons for direct control from
  the integration/device page.
- Add an Automatic updates switch that updates the configured enabled setting.

## 0.2.0 - 2026-06-20

- Add standard Home Assistant/HACS repository packaging, CI validation, project
  metadata, release changelog, and custom-component translation packaging.
- Set HACS metadata for HACS 2.0.0 and Home Assistant 2026.6.0 as the first
  release-backed support baseline.

## 0.1.1 - 2026-06-20

- Split raw pending update reporting from installable and skipped update counts.

## 0.1.0 - 2026-06-20

- Add the initial PatchPilot Home Assistant custom integration.
