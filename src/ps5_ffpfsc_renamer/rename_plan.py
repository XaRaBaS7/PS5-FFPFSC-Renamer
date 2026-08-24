from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .metadata import GameMetadata


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

    @property
    def can_apply(self) -> bool:
        return self.status is PlanStatus.READY


def _destination_for(source: Path, metadata: GameMetadata) -> Path:
    return source.with_name(f"{metadata.title_id}.ffpfsc")


def build_rename_plan(items: list[tuple[Path, GameMetadata]]) -> list[RenamePlanItem]:
    destinations: dict[str, int] = {}
    provisional: list[tuple[Path, Path, GameMetadata]] = []

    for source, metadata in items:
        source = source.resolve()
        destination = _destination_for(source, metadata)
        provisional.append((source, destination, metadata))
        key = str(destination).casefold()
        destinations[key] = destinations.get(key, 0) + 1

    result: list[RenamePlanItem] = []
    for source, destination, metadata in provisional:
        if not source.exists() or not source.is_file():
            result.append(RenamePlanItem(source, destination, metadata, PlanStatus.INVALID, "source missing"))
            continue
        if source == destination:
            result.append(RenamePlanItem(source, destination, metadata, PlanStatus.UNCHANGED, "already named"))
            continue
        if destinations[str(destination).casefold()] > 1:
            result.append(RenamePlanItem(source, destination, metadata, PlanStatus.COLLISION, "duplicate target"))
            continue
        if destination.exists():
            result.append(RenamePlanItem(source, destination, metadata, PlanStatus.COLLISION, "target exists"))
            continue
        result.append(RenamePlanItem(source, destination, metadata, PlanStatus.READY))

    return result
