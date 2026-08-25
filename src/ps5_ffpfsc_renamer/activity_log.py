from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path


_MAX_LOG_BYTES = 2 * 1024 * 1024


def default_log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "PS5-FFPFSC-Renamer" if base else Path.home() / ".ps5-ffpfsc-renamer"
    root.mkdir(parents=True, exist_ok=True)
    return root / "activity.log"


class ActivityLog:
    """Small thread-safe rolling text log used by the desktop UI."""

    def __init__(self, path: Path | None = None, max_bytes: int = _MAX_LOG_BYTES) -> None:
        self.path = (path or default_log_path()).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max(256 * 1024, int(max_bytes))
        self._lock = threading.Lock()

    def _rotate_if_needed(self) -> None:
        try:
            if not self.path.exists() or self.path.stat().st_size < self.max_bytes:
                return
            backup = self.path.with_suffix(self.path.suffix + ".1")
            try:
                backup.unlink(missing_ok=True)
            except OSError:
                pass
            self.path.replace(backup)
        except OSError:
            pass

    def write(self, level: str, message: str) -> str:
        level = (level or "INFO").strip().upper()[:10]
        compact = " | ".join(part.strip() for part in str(message).replace("\r", "").split("\n") if part.strip())
        compact = compact or "-"
        line = f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {compact}"
        with self._lock:
            self._rotate_if_needed()
            try:
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(line + "\n")
            except OSError:
                pass
        return line

    def tail(self, max_lines: int = 120) -> list[str]:
        with self._lock:
            try:
                lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                return []
        return lines[-max(1, int(max_lines)):]

    def clear(self) -> None:
        with self._lock:
            try:
                self.path.write_text("", encoding="utf-8")
            except OSError:
                pass
