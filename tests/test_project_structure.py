"""Tests for repository-level Home Assistant integration structure."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

PROJECT_DOMAIN = "patchpilot"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = PROJECT_ROOT / "custom_components" / PROJECT_DOMAIN
EXPECTED_VERSION = "0.2.0"
EXPECTED_HACS_VERSION = "2.0.0"
EXPECTED_HOME_ASSISTANT_VERSION = "2026.6.0"


def test_integration_folder_matches_project_domain() -> None:
    """The custom component folder must match the integration domain."""
    assert INTEGRATION_DIR.is_dir()


def test_manifest_domain_matches_project_domain() -> None:
    """The manifest domain must match the custom component folder."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())

    assert manifest["domain"] == PROJECT_DOMAIN


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
