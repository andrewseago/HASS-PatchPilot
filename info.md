# PatchPilot

PatchPilot installs selected pending Home Assistant `update` entities during a
configured maintenance window.

After HACS downloads the integration, restart Home Assistant and add PatchPilot
from **Settings > Devices & services**.

The configured PatchPilot entry creates one PatchPilot device with controls for
automatic updates, scanning, dry runs, and immediate update runs.

Use **Settings > Devices & services > PatchPilot > Configure** to edit the
maintenance window, include/exclude rules, exact entity exclusions, backup
behavior, and run history size.

PatchPilot exposes sensors for raw pending updates, installable updates, skipped
updates, last run, installed count, failed count, and run history.
