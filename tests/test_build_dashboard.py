from __future__ import annotations

import json
from pathlib import Path

from scripts import build_dashboard


def test_build_dashboard_has_six_panels_with_data(monkeypatch, tmp_path: Path) -> None:
    log = tmp_path / "logs.jsonl"
    rows = [
        {"ts": "2026-09-30T03:00:10Z", "event": "request_received"},
        {"ts": "2026-09-30T03:00:11Z", "event": "response_sent", "latency_ms": 400, "ttft_ms": 50,
         "tokens_in": 30, "tokens_out": 100, "cost_usd": 0.0016, "quality_score": 0.9, "tool_success": True},
        {"ts": "2026-09-30T03:01:10Z", "event": "request_received"},
        {"ts": "2026-09-30T03:01:11Z", "event": "request_failed", "error_type": "RuntimeError", "tool_success": False},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr(build_dashboard, "LOG_PATH", log)

    html = build_dashboard.build()
    data = json.loads(html.split("const D=", 1)[1].split(", colors=", 1)[0])

    assert [p["id"] for p in data["panels"]] == ["latency", "traffic", "errors", "cost", "tokens", "quality"]
    assert len(data["labels"]) == 60
    errors = next(p for p in data["panels"] if p["id"] == "errors")
    assert "error rate 50.0%" in errors["summary"]
    assert "retrieval success 50.0%" in errors["summary"]
