from __future__ import annotations

from dataclasses import dataclass

from .library_view import ResultRow
from .rename_plan import RenamePlanItem


@dataclass(slots=True)
class LibraryRecord:
    """Canonical row model used by the desktop library workspace."""

    view: ResultRow
    plan_item: RenamePlanItem | None = None
    detail: str = ""
    friendly: str = ""
    inference_source: str = ""
