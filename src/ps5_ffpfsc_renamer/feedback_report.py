from __future__ import annotations

import os
import platform
import re
import sys
import traceback
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import __version__
from .root_health import RootStatus

FEEDBACK_SCHEMA_VERSION = 1
FEEDBACK_CATEGORIES = (
    "Bug report",
    "Feature request",
    "Suggestion",
    "General feedback",
)
_MAX_TEXT = 24_000
_MAX_ACTIVITY_LINES = 80


@dataclass(frozen=True, slots=True)
class FeedbackReport:
    schema_version: int
    report_id: str
    created_at: str
    category: str
    summary: str
    description: str
    app_version: str
    diagnostics: dict[str, Any]
    exception: dict[str, str] | None = None
    activity: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "created_at": self.created_at,
            "category": self.category,
            "summary": self.summary,
            "description": self.description,
            "app_version": self.app_version,
            "diagnostics": self.diagnostics,
            "exception": self.exception,
            "activity": list(self.activity),
        }


def _clip(value: str, limit: int = _MAX_TEXT) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} character(s)]"


def _replacement_pairs(roots: Iterable[str | Path]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index, root in enumerate(roots, start=1):
        text = str(root).strip()
        if text:
            pairs.append((text, f"<ROOT_{index}>"))

    env_pairs = (
        (os.environ.get("USERPROFILE"), "<HOME>"),
        (os.environ.get("HOME"), "<HOME>"),
        (os.environ.get("LOCALAPPDATA"), "<LOCALAPPDATA>"),
        (os.environ.get("APPDATA"), "<APPDATA>"),
        (os.environ.get("TEMP"), "<TEMP>"),
        (os.environ.get("TMP"), "<TEMP>"),
    )
    for value, replacement in env_pairs:
        if value:
            pairs.append((str(value), replacement))

    try:
        home = str(Path.home())
    except Exception:
        home = ""
    if home:
        pairs.append((home, "<HOME>"))

    unique: dict[str, tuple[str, str]] = {}
    for source, replacement in pairs:
        key = source.casefold()
        if source and key not in unique:
            unique[key] = (source, replacement)
    return sorted(unique.values(), key=lambda item: len(item[0]), reverse=True)


def redact_text(value: str, *, roots: Iterable[str | Path] = ()) -> str:
    """Redact configured roots and common user-specific Windows locations."""

    text = _clip(str(value))
    for source, replacement in _replacement_pairs(roots):
        text = re.sub(re.escape(source), replacement, text, flags=re.IGNORECASE)

    # Catch user-profile paths even when environment variables were unavailable.
    text = re.sub(
        r"(?i)([A-Z]:\\Users\\)[^\\\r\n]+",
        r"\1<USER>",
        text,
    )
    text = re.sub(
        r"(?i)(/home/)[^/\r\n]+",
        r"\1<USER>",
        text,
    )

    username = os.environ.get("USERNAME") or os.environ.get("USER")
    if username and len(username) >= 3:
        text = re.sub(re.escape(username), "<USER>", text, flags=re.IGNORECASE)
    return _clip(text)


def sanitize_value(value: Any, *, roots: Iterable[str | Path] = ()) -> Any:
    if isinstance(value, str):
        return redact_text(value, roots=roots)
    if isinstance(value, Mapping):
        return {
            str(key): sanitize_value(item, roots=roots)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize_value(item, roots=roots) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value), roots=roots)


def build_exception_payload(
    exc_type: type[BaseException],
    exc_value: BaseException,
    tb,
    *,
    roots: Iterable[str | Path] = (),
) -> dict[str, str]:
    formatted = "".join(traceback.TracebackException(exc_type, exc_value, tb).format())
    return {
        "type": getattr(exc_type, "__name__", str(exc_type)),
        "message": redact_text(str(exc_value), roots=roots),
        "traceback": redact_text(formatted, roots=roots),
    }


def collect_diagnostics(
    *,
    root_statuses: Iterable[RootStatus] = (),
    record_statuses: Iterable[str] = (),
    duplicate_group_count: int = 0,
    scan_total: int = 0,
    cache_hits: int = 0,
    mkpfs_reads: int = 0,
    scan_elapsed: float = 0.0,
    worker_count: int = 1,
    scan_active: bool = False,
    live_watch: bool = False,
    watch_interval_seconds: int = 0,
    result_filter: str = "ALL",
) -> dict[str, Any]:
    root_counts = Counter(status.state for status in root_statuses)
    record_counts = Counter((status or "UNKNOWN").upper() for status in record_statuses)
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python": platform.python_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "root_states": dict(sorted(root_counts.items())),
        "record_states": dict(sorted(record_counts.items())),
        "duplicate_groups": max(0, int(duplicate_group_count)),
        "last_scan": {
            "files": max(0, int(scan_total)),
            "cache_hits": max(0, int(cache_hits)),
            "mkpfs_reads": max(0, int(mkpfs_reads)),
            "elapsed_seconds": max(0.0, round(float(scan_elapsed), 3)),
            "workers": max(1, int(worker_count)),
        },
        "scan_active": bool(scan_active),
        "live_watch": {
            "enabled": bool(live_watch),
            "interval_seconds": max(0, int(watch_interval_seconds)),
        },
        "result_filter": str(result_filter or "ALL"),
    }


def create_feedback_report(
    *,
    category: str,
    summary: str,
    description: str,
    diagnostics: Mapping[str, Any],
    roots: Iterable[str | Path] = (),
    exception: Mapping[str, str] | None = None,
    activity_lines: Iterable[str] = (),
    report_id: str | None = None,
    created_at: str | None = None,
) -> FeedbackReport:
    category = category if category in FEEDBACK_CATEGORIES else "General feedback"
    clean_roots = tuple(roots)
    clean_activity = tuple(
        redact_text(line, roots=clean_roots)
        for line in list(activity_lines)[-_MAX_ACTIVITY_LINES:]
    )
    clean_exception = (
        {
            str(key): redact_text(str(value), roots=clean_roots)
            for key, value in exception.items()
        }
        if exception
        else None
    )
    return FeedbackReport(
        schema_version=FEEDBACK_SCHEMA_VERSION,
        report_id=report_id or str(uuid.uuid4()),
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        category=category,
        summary=redact_text(summary.strip() or "Untitled feedback", roots=clean_roots),
        description=redact_text(description.strip(), roots=clean_roots),
        app_version=__version__,
        diagnostics=sanitize_value(dict(diagnostics), roots=clean_roots),
        exception=clean_exception,
        activity=clean_activity,
    )
