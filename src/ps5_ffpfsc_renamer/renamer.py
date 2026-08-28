from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .rename_plan import PlanStatus, RenamePlanItem


@dataclass(frozen=True, slots=True)
class RenameStep:
    """One filesystem mutation performed by a rename plan.

    ``mkdir`` stores the created directory in ``destination`` and leaves
    ``source`` as ``None``. ``cleanup_dir`` represents a best-effort rmdir of
    an empty source directory after a file has already been moved safely.
    Rename steps use both paths. Keeping these steps explicit lets the GUI
    persist a durable operation history and undo a completed transaction
    without touching FFPFSC contents.
    """

    kind: str
    source: Path | None
    destination: Path


class RenameTransactionError(RuntimeError):
    """Raised when a rename or its automatic rollback is incomplete."""


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
        elif item.target_directory is not None:
            steps.append(RenameStep("mkdir", None, item.target_directory))
            steps.append(RenameStep("rename_file", item.source, item.destination))
        elif item.source != item.destination:
            steps.append(RenameStep("rename_file", item.source, item.destination))

        for directory in item.cleanup_directories:
            steps.append(RenameStep("cleanup_dir", None, directory))

    return steps


def undo_forward_steps(
    steps: list[RenameStep],
    *,
    tolerate_nonempty_created_dirs: bool = True,
) -> list[Path]:
    """Reverse previously completed forward steps.

    The function never deletes files. A directory created by a forward plan is
    removed only when it is empty. A source directory removed by ``cleanup_dir``
    is recreated before its file is moved back. If the user placed anything
    else inside an application-created directory after the rename, that
    directory is deliberately left in place.
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

        if step.kind == "cleanup_dir":
            directory = step.destination
            if directory.exists():
                if not directory.is_dir():
                    raise NotADirectoryError(directory)
                continue
            directory.mkdir(parents=False, exist_ok=False)
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
        if step.kind == "cleanup_dir":
            directory = step.destination
            if not directory.exists():
                continue
            if not directory.is_dir():
                raise NotADirectoryError(directory)
            try:
                directory.rmdir()
            except OSError:
                # A cleanup step is intentionally best-effort. Any unrelated
                # content means the folder must remain untouched.
                pass
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


def _cleanup_empty_source_directories(directories: tuple[Path, ...]) -> None:
    """Remove only source directories that are empty after the file move.

    ``Path.rmdir`` is deliberately used instead of recursive deletion. Any
    unrelated file, hidden file or subdirectory makes rmdir fail and the folder
    is retained. Candidates are deepest-first so now-empty parents can also be
    removed, stopping before the selected library root.
    """
    for directory in directories:
        try:
            directory.rmdir()
        except FileNotFoundError:
            continue
        except OSError:
            # Non-empty, in use, permissions, or another filesystem condition:
            # retaining the folder is always safer than escalating to deletion.
            continue


def _apply_one(item: RenamePlanItem) -> tuple[Path, Path]:
    old_source = item.source

    # One-folder-per-game mode: rename the existing dedicated folder first,
    # then rename the FFPFSC inside it. If the file rename fails, restore the
    # old folder name.
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
        except Exception as exc:
            try:
                target_directory.rename(source_directory)
            except OSError as rollback_exc:
                raise RenameTransactionError(
                    "Folder rename failed and the original folder name could not be restored. "
                    f"Rename error: {exc}. Rollback error: {rollback_exc}"
                ) from exc
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
        except Exception as exc:
            try:
                item.target_directory.rmdir()
            except OSError as rollback_exc:
                raise RenameTransactionError(
                    "File move failed and the newly-created target folder could not be removed. "
                    f"Move error: {exc}. Cleanup error: {rollback_exc}"
                ) from exc
            raise
        return old_source, item.destination

    # Keep-current-structure or flat-root mode. The file move/rename happens
    # first. Flat-root source directories are considered for cleanup only after
    # that move has succeeded, and only empty directories can be removed.
    if item.destination.exists() and item.destination != item.source:
        raise FileExistsError(item.destination)
    item.source.rename(item.destination)
    _cleanup_empty_source_directories(item.cleanup_directories)
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
                    "Rename failed and automatic rollback of earlier completed entries was incomplete. "
                    f"Original error: {exc}. Rollback error: {rollback_exc}"
                ) from exc
            raise
    return completed
