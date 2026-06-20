"""Tests for repository-level Home Assistant integration structure."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_DOMAIN = "patchpilot"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = PROJECT_ROOT / "custom_components" / PROJECT_DOMAIN


def test_integration_folder_matches_project_domain() -> None:
    """The custom component folder must match the integration domain."""
    assert INTEGRATION_DIR.is_dir()


def test_manifest_domain_matches_project_domain() -> None:
    """The manifest domain must match the custom component folder."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())

    assert manifest["domain"] == PROJECT_DOMAIN
