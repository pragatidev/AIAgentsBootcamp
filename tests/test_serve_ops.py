"""Request id, cost report, smoke. Fixture model. No Ollama."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataflow.ops.cost import write_cost_report
from dataflow.serve import app as serve


@pytest.fixture
def ops_env(tmp_path, monkeypatch):
    log = tmp_path / "http.jsonl"
    monkeypatch.setenv("DATAFLOW_UI_MODEL", "fixture")
    monkeypatch.setenv("DATAFLOW_CHECKPOINTER", "memory")
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "refunds.jsonl"))
    monkeypatch.setenv("DATAFLOW_HTTP_LOG", str(log))
    monkeypatch.delenv("DATAFLOW_API_KEYS", raising=False)
    monkeypatch.delenv("DATAFLOW_RATE_LIMIT", raising=False)
    monkeypatch.delenv("DATAFLOW_DROP_REQUEST_ID", raising=False)
    monkeypatch.delenv("DATAFLOW_BROKEN_HEALTH", raising=False)
    monkeypatch.delenv("DATAFLOW_SKIP_INTERRUPT", raising=False)
    serve.reset_runtime()
    from fastapi.testclient import TestClient

    with TestClient(serve.app) as client:
        yield client, log, tmp_path


def test_request_id_on_header_and_trace(ops_env):
    client, log, _tmp = ops_env
    response = client.post(
        "/run",
        json={"ticket": "What is the customer return window?"},
    )
    assert response.status_code == 200
    rid = response.headers.get("x-request-id") or response.headers.get("X-Request-Id")
    assert rid
    assert log.is_file()
    rows = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert rows[-1].get("request_id") == rid


def test_smoke_passes_fixture_service(ops_env):
    client, _log, _tmp = ops_env
    health = client.get("/health")
    assert health.status_code == 200
    lookup = client.post("/run", json={"ticket": "Where is order DF-1002?"})
    assert lookup.status_code == 200
    refuse = client.post(
        "/run",
        json={"ticket": "Do you sell coffee beans in the DataFlow shop?"},
    )
    assert refuse.status_code == 200
    assert "I do not have that in the knowledge base" in refuse.json()["reply"]
    park = client.post(
        "/run",
        json={"ticket": "Please refund order DF-1001. The desk lamp is unused."},
    )
    assert park.status_code == 200
    assert park.json()["parked"] is True


def test_cost_report_has_fat_row(ops_env):
    _client, log, tmp = ops_env
    log.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "request_id": "thin-1",
            "model": "qwen3:8b",
            "tokens": {"total": 40},
            "ms": 12,
            "ticket_chars": 20,
        },
        {
            "request_id": "fat-1",
            "model": "qwen3:8b",
            "tokens": {"total": 4800},
            "ms": 1800,
            "ticket_chars": 8000,
        },
    ]
    log.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    dest = tmp / "cost_report.md"
    text = write_cost_report(log, dest, note="stuffed ticket")
    assert dest.is_file()
    assert "fat-1" in text
    assert "4800" in text
    assert "$" not in text
    assert "dollar" not in text.lower()
