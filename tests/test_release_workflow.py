from __future__ import annotations

from pathlib import Path


def test_stable_release_workflow_rejects_development_versions() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "-notmatch '^\\d+\\.\\d+\\.\\d+$'" in workflow
    assert "Refusing stable release for non-final version" in workflow


def test_stable_release_workflow_packages_official_brand_assets() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert '--add-data "assets/brand;assets/brand"' in workflow
    assert 'Copy-Item ".\\assets\\brand\\*" "$app\\assets\\brand\\"' in workflow
