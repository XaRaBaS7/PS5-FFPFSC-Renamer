from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .rename_plan import PlanStatus, RenamePlanItem


@dataclass(frozen=True, slots=True)
class RenameStep:
    """One filesystem mutation performed by a rename plan.

    ``mkdir`` stores the created directory in ``destination`` and leaves
    ``source`` as ``None``. Rename steps use both paths. Keeping these steps
    explicit lets the GUI persist a durable operation history and undo a
    completed transaction without touching FFPFSC contents.
    """

    kind: str
    source: Path | None
    destination: Path


class RenameTransactionError(RuntimeError):
    """Raised when a batch fails and rollback is incomplete."""


def build_forward_steps(plan: list[RenamePlanItem]) -> list[RenameStep]:
    """Describe the exact filesystem steps for READY entries in ``plan``."""
    steps: list[RenameStep] = []
    for item in plan:
        if item.status is not PlanStatus.READY:
            continue

        if item.source_directory is not None and item.target_directory is not None:
            steps.append(
                RenameStep("rename_dir", item.source_directory, item.target_directory)
            )
            moved_source = item.target_directory / item.source.name
            if moved_source != item.destination:
                steps.append(RenameStep("rename_file", moved_source, item.destination))
            continue

        if item.target_directory is not None:
            steps.append(RenameStep("mkdir", None, item.target_directory))
            steps.append(RenameStep("rename_file", item.source, item.destination))
            continue

        if item.source != item.destination:
            steps.append(RenameStep("rename_file", item.source, item.destination))

    return steps


def undo_forward_steps(
    steps: list[RenameStep],
    *,
    tolerate_nonempty_created_dirs: bool = True,
) -> list[Path]:
    """Reverse previously completed forward steps.

    The function never deletes files. A directory created by a forward plan is
    removed only when it is empty. If the user placed anything else inside it
    after the rename, the directory is deliberately left in place.
    """
    retained_dirs: list[Path] = []
    for step in reversed(steps):
        if step.kind in {"rename_file", "rename_dir"}:
            if step.source is None:
                raise ValueError(f"Missing source for {step.kind}")
            current = step.destination
            original = step.source
            if not current.exists():
                raise FileNotFoundError(current)
            if original.exists():
                raise FileExistsError(original)
            current.rename(original)
            continue

        if step.kind == "mkdir":
            directory = step.destination
            if not directory.exists():
                continue
            if not directory.is_dir():
                raise NotADirectoryError(directory)
            try:
                directory.rmdir()
            except OSError:
                if not tolerate_nonempty_created_dirs:
                    raise
                retained_dirs.append(directory)
            continue

        raise ValueError(f"Unsupported rename step: {step.kind}")

    return retained_dirs


def _redo_steps(steps: list[RenameStep]) -> None:
    """Re-apply steps that were reversed during a failed undo/rollback."""
    for step in steps:
        if step.kind == "mkdir":
            step.destination.mkdir(parents=False, exist_ok=False)
            continue
        if step.kind in {"rename_file", "rename_dir"}:
            if step.source is None:
                raise ValueError(f"Missing source for {step.kind}")
            if not step.source.exists():
                raise FileNotFoundError(step.source)
            if step.destination.exists():
                raise FileExistsError(step.destination)
            step.source.rename(step.destination)
            continue
        raise ValueError(f"Unsupported rename step: {step.kind}")


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
    """Apply READY entries with best-effort batch rollback on failure.

    Older versions applied entries one at a time and could leave the first
    files renamed if a later entry unexpectedly failed. v0.3 keeps the public
    return type unchanged but reverses every earlier completed entry when a
    later operation fails.
    """
    blocked = [
        item
        for item in plan
        if item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}
    ]
    if blocked:
        raise ValueError("Rename plan contains blocked entries; no files were renamed")

    completed: list[tuple[Path, Path]] = []
    completed_steps: list[RenameStep] = []
    for item in plan:
        if item.status is not PlanStatus.READY:
            continue
        try:
            completed.append(_apply_one(item))
            completed_steps.extend(build_forward_steps([item]))
        except Exception as exc:
            if not completed_steps:
                raise
            try:
                undo_forward_steps(
                    completed_steps,
                    tolerate_nonempty_created_dirs=False,
                )
            except Exception as rollback_exc:
                raise RenameTransactionError(
                    "Rename failed and automatic rollback was incomplete. "
                    f"Original error: {exc}. Rollback error: {rollback_exc}"
                ) from exc
            raise
    return completed
