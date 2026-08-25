from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .metadata import GameMetadata
from .naming import (
    FOLDER_ALWAYS_NEW,
    FOLDER_FILE_ONLY,
    FOLDER_SMART,
    NamingOptions,
    build_output_stem,
    effective_folder_handling,
)


class PlanStatus(str, Enum):
    READY = "ready"
    UNCHANGED = "unchanged"
    COLLISION = "collision"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class RenamePlanItem:
    source: Path
    destination: Path
    metadata: GameMetadata
    status: PlanStatus
    reason: str = ""
    target_directory: Path | None = None
    source_directory: Path | None = None

    @property
    def can_apply(self) -> bool:
        return self.status is PlanStatus.READY

    @property
    def renames_directory(self) -> bool:
        return self.source_directory is not None and self.target_directory is not None


def _path_key(path: Path) -> str:
    return str(path.resolve()).casefold()


def _ffpfsc_children(directory: Path) -> list[Path]:
    try:
        return [
            child
            for child in directory.iterdir()
            if child.is_file() and child.suffix.lower() == ".ffpfsc"
        ]
    except OSError as exc:
        raise ValueError(f"Unable to inspect folder {directory}: {exc}") from exc


def _resolve_library_root(source: Path, roots: tuple[Path, ...]) -> Path | None:
    """Return the most specific selected root containing source."""
    if not roots:
        return None
    source = source.resolve()
    matches: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        try:
            source.relative_to(resolved)
        except ValueError:
            continue
        matches.append(resolved)
    if not matches:
        return None
    return max(matches, key=lambda item: len(item.parts))


def _destination_for(
    source: Path,
    metadata: GameMetadata,
    options: NamingOptions,
    library_root: Path | None,
) -> tuple[Path, Path | None, Path | None]:
    stem = build_output_stem(metadata, options)
    filename = f"{stem}.ffpfsc"
    mode = effective_folder_handling(options)

    if mode == FOLDER_FILE_ONLY:
        return source.with_name(filename), None, None

    if mode == FOLDER_ALWAYS_NEW:
        target_directory = source.parent / stem
        return target_directory / filename, target_directory, None

    if mode != FOLDER_SMART:
        raise ValueError(f"Unsupported folder handling mode: {mode}")

    parent = source.parent.resolve()
    root = (library_root or parent).resolve()

    # A selected root is never renamed. A loose file directly in that root
    # receives a generated per-game folder instead.
    if _path_key(parent) == _path_key(root):
        target_directory = root / stem
        return target_directory / filename, target_directory, None

    try:
        parent.relative_to(root)
    except ValueError as exc:
        raise ValueError("source folder is outside the selected library root") from exc

    ffpfsc_files = _ffpfsc_children(parent)
    if len(ffpfsc_files) != 1:
        raise ValueError(
            f"Smart folder handling requires exactly one .ffpfsc in '{parent.name}' "
            f"(found {len(ffpfsc_files)})"
        )

    target_directory = parent.with_name(stem)

    # Folder is already correctly named: only rename the file if necessary.
    if _path_key(target_directory) == _path_key(parent):
        return parent / filename, None, None

    return target_directory / filename, target_directory, parent


def build_rename_plan(
    items: list[tuple[Path, GameMetadata]],
    options: NamingOptions | None = None,
    *,
    library_root: Path | None = None,
) -> list[RenamePlanItem]:
    options = options or NamingOptions()

    roots: list[Path] = []
    if options.library_roots:
        roots.extend(Path(value).resolve() for value in options.library_roots if value)
    elif library_root is not None:
        roots.append(library_root.resolve())
    elif options.library_root:
        roots.append(Path(options.library_root).resolve())
    roots_tuple = tuple(roots)

    destinations: dict[str, int] = {}
    directory_targets: dict[str, int] = {}
    provisional: list[
        tuple[Path, Path, Path | None, Path | None, Path | None, GameMetadata, str | None]
    ] = []

    for source, metadata in items:
        source = source.resolve()
        root = _resolve_library_root(source, roots_tuple)
        if roots_tuple and root is None:
            destination = source
            target_directory = None
            source_directory = None
            error = "source folder is outside the selected library roots"
        else:
            try:
                destination, target_directory, source_directory = _destination_for(
                    source,
                    metadata,
                    options,
                    root,
                )
                error = None
            except ValueError as exc:
                destination = source
                target_directory = None
                source_directory = None
                error = str(exc)

        provisional.append(
            (source, destination, target_directory, source_directory, root, metadata, error)
        )
        if error is None:
            destination_key = _path_key(destination)
            destinations[destination_key] = destinations.get(destination_key, 0) + 1
            if target_directory is not None:
                directory_key = _path_key(target_directory)
                directory_targets[directory_key] = directory_targets.get(directory_key, 0) + 1

    result: list[RenamePlanItem] = []
    for source, destination, target_directory, source_directory, root, metadata, error in provisional:
        def add(status: PlanStatus, reason: str = "") -> None:
            result.append(
                RenamePlanItem(
                    source=source,
                    destination=destination,
                    metadata=metadata,
                    status=status,
                    reason=reason,
                    target_directory=target_directory,
                    source_directory=source_directory,
                )
            )

        if error is not None:
            add(PlanStatus.INVALID, error)
            continue

        if not source.exists() or not source.is_file():
            add(PlanStatus.INVALID, "source missing")
            continue

        if source_directory is not None and root is not None and _path_key(source_directory) == _path_key(root):
            add(PlanStatus.INVALID, "selected library root cannot be renamed")
            continue

        if destinations[_path_key(destination)] > 1:
            add(PlanStatus.COLLISION, "duplicate file target")
            continue

        if target_directory is not None and directory_targets[_path_key(target_directory)] > 1:
            add(PlanStatus.COLLISION, "duplicate folder target")
            continue

        if target_directory is None and _path_key(source) == _path_key(destination):
            add(PlanStatus.UNCHANGED, "already named")
            continue

        if source_directory is not None and target_directory is not None:
            if not source_directory.exists() or not source_directory.is_dir():
                add(PlanStatus.INVALID, "source folder missing")
                continue
            if target_directory.exists():
                add(PlanStatus.COLLISION, "target folder already exists")
                continue
        elif target_directory is not None and target_directory.exists():
            add(PlanStatus.COLLISION, "target folder already exists")
            continue

        if destination.exists() and _path_key(destination) != _path_key(source):
            add(PlanStatus.COLLISION, "target file already exists")
            continue

        add(PlanStatus.READY)

    return result
