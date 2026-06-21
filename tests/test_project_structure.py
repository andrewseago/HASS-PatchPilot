"""Tests for repository-level Home Assistant integration structure."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

PROJECT_DOMAIN = "patchpilot"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = PROJECT_ROOT / "custom_components" / PROJECT_DOMAIN
EXPECTED_VERSION = "0.3.8"
EXPECTED_HACS_VERSION = "2.0.0"
EXPECTED_HOME_ASSISTANT_VERSION = "2026.6.0"


def test_integration_folder_matches_project_domain() -> None:
    """The custom component folder must match the integration domain."""
    assert INTEGRATION_DIR.is_dir()


def test_manifest_domain_matches_project_domain() -> None:
    """The manifest domain must match the custom component folder."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())

    assert manifest["domain"] == PROJECT_DOMAIN


def test_manifest_exposes_patchpilot_as_single_service_entry() -> None:
    """PatchPilot should be a normal service integration with one config entry."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())

    assert manifest["integration_type"] == "service"
    assert manifest["single_config_entry"] is True


def test_repository_has_standard_integration_files() -> None:
    """The repo should include the normal custom-integration support files."""
    expected_paths = (
        ".gitattributes",
        ".github/workflows/build.yaml",
        ".pre-commit-config.yaml",
        "CHANGELOG.md",
        "hacs.json",
        "info.md",
        "pyproject.toml",
        "requirements.txt",
        "requirements_dev.txt",
        "custom_components/__init__.py",
        "custom_components/patchpilot/button.py",
        "custom_components/patchpilot/entity.py",
        "custom_components/patchpilot/switch.py",
        "custom_components/patchpilot/translations/en.json",
    )

    for path in expected_paths:
        assert (PROJECT_ROOT / path).is_file(), path


def test_version_metadata_is_consistent() -> None:
    """The manifest, project metadata, and changelog must use one version."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text()

    assert manifest["version"] == EXPECTED_VERSION
    assert project["project"]["version"] == EXPECTED_VERSION
    assert f"## {EXPECTED_VERSION} -" in changelog


def test_hacs_metadata_matches_manifest() -> None:
    """HACS metadata should match the integration manifest and HA baseline."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())
    hacs = json.loads((PROJECT_ROOT / "hacs.json").read_text())

    assert hacs["name"] == manifest["name"]
    assert hacs["hacs"] == EXPECTED_HACS_VERSION
    assert hacs["homeassistant"] == EXPECTED_HOME_ASSISTANT_VERSION


def test_custom_component_translation_is_packaged() -> None:
    """Custom-component installs need a generated English translation file."""
    strings = json.loads((INTEGRATION_DIR / "strings.json").read_text())
    translation = json.loads((INTEGRATION_DIR / "translations" / "en.json").read_text())

    assert translation == strings


def test_ci_workflow_validates_hacs_hassfest_and_tests() -> None:
    """The GitHub workflow should run HACS, Hassfest, and the local tests."""
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "build.yaml").read_text()

    assert "hacs/action" in workflow
    assert "home-assistant/actions/hassfest" in workflow
    assert "python-version: ${{ env.DEFAULT_PYTHON }}" in workflow
    assert "pytest" in workflow


def test_integration_forwards_ui_control_platforms() -> None:
    """PatchPilot should expose native UI controls under its config entry."""
    const_source = (INTEGRATION_DIR / "const.py").read_text()
    init_source = (INTEGRATION_DIR / "__init__.py").read_text()

    assert 'PLATFORMS = ["button", "sensor", "switch"]' in const_source
    assert "async_forward_entry_setups(entry, PLATFORMS)" in init_source


def test_entities_share_patchpilot_device_info() -> None:
    """Entities should be grouped as one PatchPilot device in the UI."""
    entity_source = (INTEGRATION_DIR / "entity.py").read_text()
    sensor_source = (INTEGRATION_DIR / "sensor.py").read_text()
    switch_source = (INTEGRATION_DIR / "switch.py").read_text()
    button_source = (INTEGRATION_DIR / "button.py").read_text()

    assert "DeviceInfo" in entity_source
    assert "identifiers={(DOMAIN, self.manager.entry.entry_id)}" in entity_source
    assert (
        'configuration_url=f"homeassistant://config/integrations/integration/{DOMAIN}"'
        in entity_source
    )
    assert (
        "class PatchPilotSensor(PatchPilotObservableEntity, SensorEntity)"
        in sensor_source
    )
    assert (
        "class PatchPilotSwitch(PatchPilotObservableEntity, SwitchEntity)"
        in switch_source
    )
    assert "class PatchPilotButton(PatchPilotEntity, ButtonEntity)" in button_source


def test_ui_control_entities_call_manager_actions() -> None:
    """Button and switch entities should expose the configured service actions."""
    switch_source = (INTEGRATION_DIR / "switch.py").read_text()
    button_source = (INTEGRATION_DIR / "button.py").read_text()
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()

    assert "async_set_enabled" in manager_source
    assert "await self.manager.async_set_enabled(True)" in switch_source
    assert "await self.manager.async_set_enabled(False)" in switch_source
    assert "await self.manager.async_scan()" in button_source
    assert 'reason="button_dry_run"' in button_source
    assert "dry_run=True" in button_source
    assert 'reason="button"' in button_source
    assert "ignore_window=True" in button_source


def test_config_flow_does_not_block_stale_hidden_entries() -> None:
    """Adding PatchPilot should not hard-abort on a stale hidden config entry."""
    config_flow_source = (INTEGRATION_DIR / "config_flow.py").read_text()
    strings_source = (INTEGRATION_DIR / "strings.json").read_text()

    assert "async_set_unique_id(DOMAIN)" not in config_flow_source
    assert "_abort_if_unique_id_configured" not in config_flow_source
    assert "already_configured" not in strings_source


def test_manager_only_requests_restart_for_ha_runtime_updates() -> None:
    """PatchPilot should not ask for an HA restart after external updates."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()
    update_logic_source = (INTEGRATION_DIR / "update_logic.py").read_text()

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
    assert '"title": "PatchPilot restart required"' in manager_source
    assert '"title": "PatchPilot updates installed"' in manager_source
    assert "_restart_required" in manager_source


def test_manager_lists_skipped_updates_after_runs() -> None:
    """PatchPilot should list skipped pending updates and why they were skipped."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()
    sensor_source = (INTEGRATION_DIR / "sensor.py").read_text()

    assert "filtered: list[str]" in manager_source
    assert "uninstallable: list[str]" in manager_source
    assert "result.filtered = [" in manager_source
    assert "result.uninstallable = [" in manager_source
    assert "await self._async_notify_skipped_updates(result)" in manager_source
    assert "async def _async_notify_skipped_updates" in manager_source
    assert "Filtered by PatchPilot configuration" in manager_source
    assert "Pending but not installable through Home Assistant" in manager_source
    assert "await self._async_clear_skipped_updates_notification()" in manager_source
    assert '"skipped": result.filtered + result.uninstallable' in manager_source
    assert '"filtered": result.filtered' in manager_source
    assert '"uninstallable": result.uninstallable' in manager_source
    assert '"skipped": result.filtered + result.uninstallable' in sensor_source


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


def test_manager_debounces_update_state_change_runs() -> None:
    """Update-state bursts should schedule one delayed run, not one run per event."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()

    assert "STATE_CHANGE_DEBOUNCE_SECONDS = 5" in manager_source
    assert "self._state_change_task: asyncio.Task[None] | None = None" in manager_source
    assert "async def _async_run_after_state_change_delay" in manager_source
    assert "await asyncio.sleep(STATE_CHANGE_DEBOUNCE_SECONDS)" in manager_source
    assert "if self._state_change_task is not None" in manager_source
    assert "and not self._state_change_task.done()" in manager_source
    assert "self._state_change_task.cancel()" in manager_source


def test_state_change_runs_respect_automatic_update_window() -> None:
    """State-change auto-runs should not spam outside-window skipped history."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()

    assert "if not self.enabled or not self._inside_window():" in manager_source
    assert "return" in manager_source


def test_manager_finishes_runs_when_post_run_refresh_fails() -> None:
    """A post-install scan failure should be retained on the completed run."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()
    sensor_source = (INTEGRATION_DIR / "sensor.py").read_text()

    assert "scan_failed: str | None = None" in manager_source
    assert "async def _async_refresh_after_run" in manager_source
    assert "result.scan_failed = str(err)" in manager_source
    assert 'failed", result.reason' in manager_source
    assert '"scan_failed": result.scan_failed' in manager_source
    assert '"scan_failed": result.scan_failed' in sensor_source


def test_manager_notifications_are_best_effort() -> None:
    """Persistent-notification failures should not abort update runs."""
    manager_source = (INTEGRATION_DIR / "manager.py").read_text()

    assert "async def _async_update_notifications" in manager_source
    assert "await self._async_update_notifications(result)" in manager_source
    assert "Failed updating PatchPilot notifications after %s run" in manager_source
    assert "await self._async_notify_failure(result)" in manager_source
    assert "await self._async_notify_restart_required(result)" in manager_source
    assert "await self._async_notify_skipped_updates(result)" in manager_source
    assert "await self._async_clear_skipped_updates_notification()" in manager_source
