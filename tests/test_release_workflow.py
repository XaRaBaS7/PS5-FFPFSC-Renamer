from __future__ import annotations

from pathlib import Path


def test_release_workflow_accepts_numeric_and_lettered_prereleases_only() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "-notmatch '^\\d+\\.\\d+\\.\\d+(?:[a-z]\\d*)?$'" in workflow
    assert "Expected X.Y.Z or X.Y.Z<letter>[number]" in workflow
    assert "$isPrerelease = $version -notmatch '^\\d+\\.\\d+\\.\\d+$'" in workflow
    assert '--prerelease' in workflow


def test_stable_release_workflow_bundles_branding_without_duplicate_root_assets() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert '--add-data "assets/brand;assets/brand"' in workflow
    assert 'Copy-Item ".\\assets\\brand\\*" "$app\\assets\\brand\\"' not in workflow
    assert 'Copy-Item ".\\assets\\app-icon.png" "$app\\app-icon.png"' not in workflow
    assert 'Unexpected redundant app-icon.png in package root' in workflow
    assert 'Unexpected redundant assets directory in package root' in workflow
    assert 'Bundled brand assets are missing' in workflow


def test_v050_release_workflow_never_recreates_or_moves_historical_tag() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    historical_commit = "599bf32344c039d47593c135814744d3eec654a9"

    assert 'if ($tag -eq "v0.5.0")' in workflow
    assert historical_commit in workflow
    assert "Historical tag v0.5.0 is missing. Refusing to recreate it on current main." in workflow
    assert "Refusing release upload." in workflow
    assert 'elseif (-not $exists)' in workflow
    assert "Historical v0.5.0 release is missing. Refusing to create a replacement release." in workflow


def test_release_zip_keeps_versioned_top_level_folder() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert '$package = ".\\dist\\PS5-FFPFSC-Renamer-v$version-Windows-x64"' in workflow
    assert "Move-Item $app $package" in workflow
    assert 'Compress-Archive -Path $package -DestinationPath $archive -Force' in workflow
    assert 'Compress-Archive -Path "$app\\*"' not in workflow
