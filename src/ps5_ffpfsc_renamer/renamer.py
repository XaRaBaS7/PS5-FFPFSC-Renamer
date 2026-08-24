from __future__ import annotations

from pathlib import Path

from .rename_plan import PlanStatus, RenamePlanItem


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

        if item.destination.exists():
            raise FileExistsError(item.destination)

        created_directory = False
        if item.target_directory is not None:
            if item.target_directory.exists() and not item.target_directory.is_dir():
                raise FileExistsError(item.target_directory)
            if not item.target_directory.exists():
                item.target_directory.mkdir(parents=False, exist_ok=False)
                created_directory = True

        try:
            item.source.rename(item.destination)
        except Exception:
            if created_directory:
                try:
                    item.target_directory.rmdir()  # type: ignore[union-attr]
                except OSError:
                    pass
            raise

        completed.append((item.source, item.destination))
    return completed
