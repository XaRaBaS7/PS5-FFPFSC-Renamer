from __future__ import annotations

from pathlib import Path

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import FOLDER_FILE_ONLY, NamingOptions
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

    completed = apply_rename_plan(plan)
    verification = verify_completed_rename(preflight, completed)

    assert verification.passed
    assert verification.checked_count == 1
    assert verification.verified_count == 1


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
