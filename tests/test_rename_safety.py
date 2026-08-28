from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import FOLDER_FILE_ONLY, FOLDER_ROOT_FLAT, NamingOptions
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, build_rename_plan
from ps5_ffpfsc_renamer.rename_safety import preflight_rename, verify_completed_rename
from ps5_ffpfsc_renamer.renamer import apply_rename_plan


def test_preflight_and_verification_preserve_file_identity(tmp_path: Path) -> None:
    source = tmp_path / "Returnal Backup.ffpfsc"
    source.write_bytes((b"rename-safety" * 4096) + bytes(range(256)))
    metadata = GameMetadata(title_id="PPSA01285", title_name="Returnal")
    options = NamingOptions(
        include_title_id=True,
        folder_handling=FOLDER_FILE_ONLY,
        library_roots=(str(tmp_path),),
    )
    plan = build_rename_plan([(source, metadata)], options)
    assert plan[0].status is PlanStatus.READY

    preflight = preflight_rename(plan)
    assert preflight.can_apply
    assert preflight.ready_count == 1
    assert preflight.blocked_count == 0
    assert preflight.total_bytes == source.stat().st_size
    assert preflight.directories_cleanup_candidates == 0

    completed = apply_rename_plan(plan)
    verification = verify_completed_rename(preflight, completed)

    assert verification.passed
    assert verification.checked_count == 1
    assert verification.verified_count == 1


def test_flat_root_preflight_reports_unique_source_folder_cleanup_candidates(tmp_path: Path) -> None:
    shared = tmp_path / "Shared" / "Nested"
    shared.mkdir(parents=True)
    first = shared / "one.ffpfsc"
    second = shared / "two.ffpfsc"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    options = NamingOptions(
        include_title_id=True,
        folder_handling=FOLDER_ROOT_FLAT,
        library_roots=(str(tmp_path),),
    )
    plan = build_rename_plan(
        [
            (first, GameMetadata(title_id="PPSA00001")),
            (second, GameMetadata(title_id="PPSA00002")),
        ],
        options,
    )
    preflight = preflight_rename(plan)

    assert preflight.can_apply
    assert preflight.ready_count == 2
    assert preflight.directories_cleanup_candidates == 2  # Nested + Shared, counted once each.


def test_preflight_blocks_destination_that_appears_after_preview(tmp_path: Path) -> None:
    source = tmp_path / "source.ffpfsc"
    source.write_bytes(b"source")
    metadata = GameMetadata(title_id="PPSA40001")
    options = NamingOptions(
        include_title_id=True,
        folder_handling=FOLDER_FILE_ONLY,
        library_roots=(str(tmp_path),),
    )
    plan = build_rename_plan([(source, metadata)], options)
    assert plan[0].status is PlanStatus.READY

    plan[0].destination.write_bytes(b"late collision")
    preflight = preflight_rename(plan)

    assert not preflight.can_apply
    assert preflight.errors
    assert "destination appeared after preview" in preflight.errors[0]
