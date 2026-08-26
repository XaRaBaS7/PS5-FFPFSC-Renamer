from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .workspace_models import LibraryRecord as _Record

__all__ = ["_Record", "RenamerApp"]

if TYPE_CHECKING:
    from .gui_v9_legacy import RenamerApp as RenamerApp


def __getattr__(name: str) -> Any:
    """Load the historical v9 class only when legacy callers request it."""
    if name == "RenamerApp":
        from .gui_v9_legacy import RenamerApp as legacy_app

        globals()[name] = legacy_app
        return legacy_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
