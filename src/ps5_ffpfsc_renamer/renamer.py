from __future__ import annotations

from pathlib import Path

from .rename_plan import PlanStatus, RenamePlanItem


def apply_rename_plan(plan: list[RenamePlanItem]) -> list[tuple[Path, Path]]:
    blocked = [item for item in plan if item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}]
    if blocked:
        raise ValueError("Rename plan contains blocked entries; no files were renamed")

    completed: list[tuple[Path, Path]] = []
    for item in plan:
        if item.status is not PlanStatus.READY:
            continue
        if item.destination.exists():
            raise FileExistsError(item.destination)
        item.source.rename(item.destination)
        completed.append((item.source, item.destination))
    return completed
