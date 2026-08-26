from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class RootStatus:
    path: Path
    state: str
    detail: str = ""

    @property
    def available(self) -> bool:
        return self.state == "ONLINE"


def root_key(path: Path) -> str:
    """Return a stable lexical identity without probing the filesystem."""

    expanded = os.path.expanduser(str(path))
    normalized = os.path.normcase(os.path.abspath(expanded))
    return normalized.casefold()


def probe_root(path: Path) -> RootStatus:
    raw = Path(path).expanduser()
    try:
        normalized = raw.resolve(strict=False)
    except OSError:
        normalized = raw.absolute()
    try:
        if not normalized.exists():
            return RootStatus(normalized, "OFFLINE", "path is not currently available")
        if not normalized.is_dir():
            return RootStatus(normalized, "ERROR", "selected root is not a directory")
    except OSError as exc:
        return RootStatus(normalized, "ERROR", str(exc))
    return RootStatus(normalized, "ONLINE", "available")


def probe_roots(paths: Iterable[Path]) -> dict[str, RootStatus]:
    """Probe roots while preserving the lexical identity selected by the user."""

    result: dict[str, RootStatus] = {}
    for path in paths:
        configured = Path(path)
        status = probe_root(configured)
        # A junction/symlink may resolve to a different physical path. UI and
        # settings lookup must remain keyed by the configured root, otherwise
        # the selected location would incorrectly appear UNKNOWN.
        result[root_key(configured)] = status
    return result
