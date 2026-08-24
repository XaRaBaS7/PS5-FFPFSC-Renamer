from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .metadata import GameMetadata
from .naming import NamingOptions, build_output_stem


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

    @property
    def can_apply(self) -> bool:
        return self.status is PlanStatus.READY


def _destination_for(
    source: Path,
    metadata: GameMetadata,
    options: NamingOptions,
) -> tuple[Path, Path | None]:
    stem = build_output_stem(metadata, options)
    filename = f"{stem}.ffpfsc"
    if options.create_folder:
        directory = source.parent / stem
        return directory / filename, directory
    return source.with_name(filename), None


def build_rename_plan(
    items: list[tuple[Path, GameMetadata]],
    options: NamingOptions | None = None,
) -> list[RenamePlanItem]:
    options = options or NamingOptions()
    destinations: dict[str, int] = {}
    provisional: list[tuple[Path, Path, Path | None, GameMetadata, str | None]] = []

    for source, metadata in items:
        source = source.resolve()
        try:
            destination, target_directory = _destination_for(source, metadata, options)
            error = None
        except ValueError as exc:
            destination = source
            target_directory = None
            error = str(exc)

        provisional.append((source, destination, target_directory, metadata, error))
        if error is None:
            key = str(destination).casefold()
            destinations[key] = destinations.get(key, 0) + 1

    result: list[RenamePlanItem] = []
    for source, destination, target_directory, metadata, error in provisional:
        if error is not None:
            result.append(
                RenamePlanItem(
                    source,
                    destination,
                    metadata,
                    PlanStatus.INVALID,
                    error,
                    target_directory,
                )
            )
            continue

        if not source.exists() or not source.is_file():
            result.append(
                RenamePlanItem(
                    source,
                    destination,
                    metadata,
                    PlanStatus.INVALID,
                    "source missing",
                    target_directory,
                )
            )
            continue

        if target_directory is None and source == destination:
            result.append(
                RenamePlanItem(
                    source,
                    destination,
                    metadata,
                    PlanStatus.UNCHANGED,
                    "already named",
                    target_directory,
                )
            )
            continue

        if destinations[str(destination).casefold()] > 1:
            result.append(
                RenamePlanItem(
                    source,
                    destination,
                    metadata,
                    PlanStatus.COLLISION,
                    "duplicate target",
                    target_directory,
                )
            )
            continue

        if destination.exists():
            result.append(
                RenamePlanItem(
                    source,
                    destination,
                    metadata,
                    PlanStatus.COLLISION,
                    "target exists",
                    target_directory,
                )
            )
            continue

        if target_directory is not None and target_directory.exists() and not target_directory.is_dir():
            result.append(
                RenamePlanItem(
                    source,
                    destination,
                    metadata,
                    PlanStatus.COLLISION,
                    "folder target is occupied by a file",
                    target_directory,
                )
            )
            continue

        result.append(
            RenamePlanItem(
                source,
                destination,
                metadata,
                PlanStatus.READY,
                target_directory=target_directory,
            )
        )

    return result
