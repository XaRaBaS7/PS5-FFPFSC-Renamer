from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .feedback_report import FeedbackReport

FEEDBACK_ENDPOINT_ENV = "PS5_FFPFSC_FEEDBACK_ENDPOINT"
DEFAULT_FEEDBACK_ENDPOINT = ""
_MAX_RESPONSE_BYTES = 4096


@dataclass(frozen=True, slots=True)
class FeedbackDelivery:
    sent: bool
    detail: str
    queued_path: Path | None = None
    status_code: int | None = None


def default_feedback_queue_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "PS5-FFPFSC-Renamer" if base else Path.home() / ".ps5-ffpfsc-renamer"
    return root / "feedback-queue"


def _payload(report: FeedbackReport | Mapping[str, Any]) -> dict[str, Any]:
    return report.payload() if isinstance(report, FeedbackReport) else dict(report)


def _safe_report_id(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "feedback")).strip(".-")
    return text[:100] or "feedback"


def queue_feedback_report(
    report: FeedbackReport | Mapping[str, Any],
    *,
    queue_dir: Path | None = None,
) -> Path:
    payload = _payload(report)
    directory = queue_dir or default_feedback_queue_dir()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{_safe_report_id(payload.get('report_id'))}.json"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_queued_feedback(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("queued feedback payload must be a JSON object")
    return payload


def queued_feedback_reports(*, queue_dir: Path | None = None) -> tuple[Path, ...]:
    directory = queue_dir or default_feedback_queue_dir()
    try:
        items = [path for path in directory.glob("*.json") if path.is_file()]
    except OSError:
        return ()
    return tuple(sorted(items, key=lambda path: path.name.casefold()))


def resolve_feedback_endpoint(explicit: str | None = None) -> str | None:
    value = (explicit or os.environ.get(FEEDBACK_ENDPOINT_ENV) or DEFAULT_FEEDBACK_ENDPOINT).strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        return value
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return value
    raise ValueError("feedback endpoint must use HTTPS (HTTP is allowed only for localhost testing)")


def submit_feedback_payload(
    payload: Mapping[str, Any],
    *,
    endpoint: str | None = None,
    timeout: float = 12.0,
) -> FeedbackDelivery:
    try:
        target = resolve_feedback_endpoint(endpoint)
    except ValueError as exc:
        return FeedbackDelivery(False, str(exc))
    if target is None:
        return FeedbackDelivery(False, "Direct feedback endpoint is not configured in this build.")

    body = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(
        target,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "PS5-FFPFSC-Renamer-Feedback/1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=max(1.0, float(timeout))) as response:
            status = int(getattr(response, "status", 200))
            response.read(_MAX_RESPONSE_BYTES)
        if 200 <= status < 300:
            return FeedbackDelivery(True, "Feedback report submitted successfully.", status_code=status)
        return FeedbackDelivery(False, f"Feedback server returned HTTP {status}.", status_code=status)
    except HTTPError as exc:
        return FeedbackDelivery(False, f"Feedback server returned HTTP {exc.code}.", status_code=int(exc.code))
    except URLError as exc:
        return FeedbackDelivery(False, f"Feedback server unavailable: {exc.reason}")
    except OSError as exc:
        return FeedbackDelivery(False, f"Feedback submission failed: {exc}")


def send_or_queue_feedback(
    report: FeedbackReport | Mapping[str, Any],
    *,
    endpoint: str | None = None,
    queue_dir: Path | None = None,
    timeout: float = 12.0,
) -> FeedbackDelivery:
    payload = _payload(report)
    queued = queue_feedback_report(payload, queue_dir=queue_dir)
    result = submit_feedback_payload(payload, endpoint=endpoint, timeout=timeout)
    if not result.sent:
        return FeedbackDelivery(
            False,
            result.detail,
            queued_path=queued,
            status_code=result.status_code,
        )
    try:
        queued.unlink(missing_ok=True)
    except OSError:
        pass
    return FeedbackDelivery(True, result.detail, status_code=result.status_code)
