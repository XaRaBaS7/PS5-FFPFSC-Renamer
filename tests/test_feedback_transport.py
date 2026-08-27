from __future__ import annotations

import json
from pathlib import Path

import ps5_ffpfsc_renamer.feedback_transport as transport
from ps5_ffpfsc_renamer.feedback_report import create_feedback_report


def _report():
    return create_feedback_report(
        category="Bug report",
        summary="Example",
        description="Example description",
        diagnostics={"state": "READY"},
        report_id="report-123",
        created_at="2026-08-26T20:00:00+00:00",
    )


def test_feedback_queue_round_trip(tmp_path: Path) -> None:
    report = _report()
    path = transport.queue_feedback_report(report, queue_dir=tmp_path)

    assert path.name == "report-123.json"
    assert transport.queued_feedback_reports(queue_dir=tmp_path) == (path,)
    payload = transport.load_queued_feedback(path)
    assert payload["report_id"] == "report-123"
    assert payload["category"] == "Bug report"


def test_feedback_endpoint_requires_https_except_localhost(monkeypatch) -> None:
    monkeypatch.delenv(transport.FEEDBACK_ENDPOINT_ENV, raising=False)
    assert transport.DEFAULT_FEEDBACK_ENDPOINT.startswith("https://")
    assert transport.resolve_feedback_endpoint() == transport.DEFAULT_FEEDBACK_ENDPOINT
    assert transport.resolve_feedback_endpoint("https://example.invalid/report") == "https://example.invalid/report"
    assert transport.resolve_feedback_endpoint("http://localhost:8080/report") == "http://localhost:8080/report"

    try:
        transport.resolve_feedback_endpoint("http://example.invalid/report")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("non-local HTTP endpoint was accepted")


def test_feedback_health_reports_missing_endpoint(monkeypatch) -> None:
    monkeypatch.delenv(transport.FEEDBACK_ENDPOINT_ENV, raising=False)
    monkeypatch.setattr(transport, "DEFAULT_FEEDBACK_ENDPOINT", "")
    health = transport.feedback_endpoint_health()
    assert health.configured is False
    assert health.available is False
    assert "not configured" in health.detail


def test_feedback_health_accepts_expected_receiver(monkeypatch) -> None:
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _limit):
            return json.dumps(
                {
                    "ok": True,
                    "service": transport.FEEDBACK_SERVICE_NAME,
                    "schema_version": 1,
                }
            ).encode("utf-8")

    captured = {}

    def fake_urlopen(request, timeout):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(transport, "urlopen", fake_urlopen)
    health = transport.feedback_endpoint_health(
        endpoint="https://feedback.example.invalid/report",
        timeout=2,
    )

    assert health.configured is True
    assert health.available is True
    assert health.status_code == 200
    assert captured["method"] == "GET"
    assert captured["url"] == "https://feedback.example.invalid/report"


def test_feedback_health_rejects_unrelated_https_page(monkeypatch) -> None:
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _limit):
            return b'{"ok":true,"service":"something-else"}'

    monkeypatch.setattr(transport, "urlopen", lambda _request, timeout: _Response())
    health = transport.feedback_endpoint_health(endpoint="https://example.invalid/")

    assert health.configured is True
    assert health.available is False
    assert "did not identify itself" in health.detail


def test_send_or_queue_keeps_report_when_endpoint_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(transport.FEEDBACK_ENDPOINT_ENV, raising=False)
    monkeypatch.setattr(transport, "DEFAULT_FEEDBACK_ENDPOINT", "")
    result = transport.send_or_queue_feedback(_report(), queue_dir=tmp_path)

    assert result.sent is False
    assert result.queued_path is not None
    assert result.queued_path.exists()
    assert "not configured" in result.detail


def test_send_or_queue_removes_local_copy_after_success(tmp_path: Path, monkeypatch) -> None:
    class _Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _limit):
            return b'{"accepted":true}'

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr(transport, "urlopen", fake_urlopen)
    result = transport.send_or_queue_feedback(
        _report(),
        endpoint="https://feedback.example.invalid/report",
        queue_dir=tmp_path,
        timeout=3,
    )

    assert result.sent is True
    assert result.status_code == 202
    assert transport.queued_feedback_reports(queue_dir=tmp_path) == ()
    assert captured["url"] == "https://feedback.example.invalid/report"
    assert captured["payload"]["report_id"] == "report-123"
