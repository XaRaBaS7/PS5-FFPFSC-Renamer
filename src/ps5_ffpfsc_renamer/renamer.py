from __future__ import annotations

from pathlib import Path

from .rename_plan import PlanStatus, RenamePlanItem


def _apply_one(item: RenamePlanItem) -> tuple[Path, Path]:
    old_source = item.source

    # Smart mode: rename the existing dedicated folder first, then rename the
    # FFPFSC inside it. If the file rename fails, try to restore the old folder
    # name so the operation does not leave a half-applied layout.
    if item.source_directory is not None and item.target_directory is not None:
        source_directory = item.source_directory
        target_directory = item.target_directory

        if target_directory.exists():
            raise FileExistsError(target_directory)
        if not source_directory.is_dir():
            raise FileNotFoundError(source_directory)

        source_directory.rename(target_directory)
        moved_source = target_directory / old_source.name
        try:
            if moved_source != item.destination:
                if item.destination.exists():
                    raise FileExistsError(item.destination)
                moved_source.rename(item.destination)
        except Exception:
            try:
                target_directory.rename(source_directory)
            except OSError:
                pass
            raise

        return old_source, item.destination

    # Folder creation mode: create a fresh per-game directory and move the
    # file into it. Existing folders are blocked by the plan before this point.
    if item.target_directory is not None:
        if item.target_directory.exists():
            raise FileExistsError(item.target_directory)

        item.target_directory.mkdir(parents=False, exist_ok=False)
        try:
            item.source.rename(item.destination)
        except Exception:
            try:
                item.target_directory.rmdir()
            except OSError:
                pass
            raise
        return old_source, item.destination

    # File-only mode, or Smart mode where the folder name was already correct.
    if item.destination.exists() and item.destination != item.source:
        raise FileExistsError(item.destination)
    item.source.rename(item.destination)
    return old_source, item.destination


def apply_rename_plan(plan: list[RenamePlanItem]) -> list[tuple[Path, Path]]:
    blocked = [
        item
        for item in plan
        if item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}
    ]
    if blocked:
        raise ValueError("Rename plan contains blocked entries; no files were renamed")

    completed: list[tuple[Path, Path]] = []
    for item in plan:
        if item.status is not PlanStatus.READY:
            continue
        completed.append(_apply_one(item))
    return completed
