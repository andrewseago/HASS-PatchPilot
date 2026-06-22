# Changelog

## 0.4.1 - 2026-06-22

- Fix a 500 error when opening **Configure**: the options flow no longer
  assigns the now read-only `OptionsFlow.config_entry` property. Home
  Assistant supplies it automatically.

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

## 0.3.8 - 2026-06-20

- Only request a Home Assistant restart for installed updates that affect the
  Home Assistant runtime, such as HACS-managed updates and Home Assistant Core.
- Send a non-restart completion notification for external device or service
  updates, such as OPNsense firmware, while still listing skipped updates.
- Expose restart-required installed entities in last-run attributes and retained
  run history.

## 0.3.7 - 2026-06-20

- Make state-change-triggered automatic runs respect the enabled setting and
  maintenance window before scheduling a run, preventing outside-window
  state-change events from filling run history with skipped entries.

## 0.3.6 - 2026-06-20

- Debounce update-state-change triggers so bursts of update entity changes create
  one delayed PatchPilot run instead of redundant serialized runs.
- Keep update run history and last-run attributes even when a post-run entity
  refresh fails.
- Treat persistent notification failures as best effort so notification service
  issues do not abort update run completion.
- Expose post-run scan failures through last-run attributes and run history.

## 0.3.5 - 2026-06-20

- Add a PatchPilot device configuration URL that opens the integration
  configuration page from the service/device UI.

## 0.3.4 - 2026-06-20

- List skipped pending updates by reason in PatchPilot run history, last-run
  attributes, and persistent notifications.

## 0.3.3 - 2026-06-20

- Add a persistent notification requesting a Home Assistant restart after
  PatchPilot finishes installing one or more updates.

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
