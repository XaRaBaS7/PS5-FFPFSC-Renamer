from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.root_health import RootStatus, root_key
from ps5_ffpfsc_renamer.ui.optimized_scan_mixin import (
    _mark_effective_root_error,
    _record_configured_root_status,
)


def test_probe_status_is_keyed_by_configured_root(tmp_path: Path) -> None:
    configured = tmp_path / "configured-alias"
    physical = tmp_path / "physical-library"
    status = RootStatus(physical, "ONLINE", "available")
    statuses: dict[str, RootStatus] = {}

    _record_configured_root_status(statuses, configured, status)

    assert statuses[root_key(configured)] is status
    assert root_key(physical) not in statuses


def test_discovery_error_maps_back_to_all_configured_roots_it_covered(
    tmp_path: Path,
) -> None:
    physical_parent = tmp_path / "physical-library"
    physical_child = physical_parent / "nested"
    parent_alias = tmp_path / "parent-alias"
    child_alias = tmp_path / "child-alias"
    offline_alias = tmp_path / "offline-alias"
    offline_path = tmp_path / "offline-target"

    parent_status = RootStatus(physical_parent, "ONLINE", "available")
    child_status = RootStatus(physical_child, "ONLINE", "available")
    offline_status = RootStatus(offline_path, "OFFLINE", "unavailable")
    probes = [
        (parent_alias, parent_status),
        (child_alias, child_status),
        (offline_alias, offline_status),
    ]
    statuses = {
        root_key(parent_alias): parent_status,
        root_key(child_alias): child_status,
        root_key(offline_alias): offline_status,
    }

    affected = _mark_effective_root_error(
        statuses,
        probes,
        physical_parent,
        "directory traversal failed",
    )

    assert affected == (parent_alias, child_alias)
    assert statuses[root_key(parent_alias)].state == "ERROR"
    assert statuses[root_key(child_alias)].state == "ERROR"
    assert statuses[root_key(offline_alias)] is offline_status
    assert root_key(physical_parent) not in statuses
