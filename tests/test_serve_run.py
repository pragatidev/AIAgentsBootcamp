"""POST /run door. Pytest stays green with the fixture model."""

from __future__ import annotations

from pathlib import Path

import pytest

from dataflow.serve import app as serve


@pytest.fixture
def run_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAFLOW_UI_MODEL", "fixture")
    monkeypatch.setenv("DATAFLOW_CHECKPOINTER", "memory")
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "refunds.jsonl"))
    monkeypatch.setenv("DATAFLOW_HTTP_LOG", str(tmp_path / "http.jsonl"))
    monkeypatch.delenv("DATAFLOW_API_KEYS", raising=False)
    monkeypatch.delenv("DATAFLOW_RATE_LIMIT", raising=False)
    monkeypatch.delenv("DATAFLOW_SKIP_API_KEY", raising=False)
    monkeypatch.delenv("DATAFLOW_BROKEN_HEALTH", raising=False)
    monkeypatch.delenv("DATAFLOW_DROP_REQUEST_ID", raising=False)
    monkeypatch.delenv("DATAFLOW_SKIP_INTERRUPT", raising=False)
    monkeypatch.delenv("DATAFLOW_RATE_LIMIT_OFF", raising=False)
    serve.reset_runtime()
    from fastapi.testclient import TestClient

    with TestClient(serve.app) as client:
        yield client


def test_health_ok(run_client):
    response = run_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "dataflow"


def test_run_free_text_422(run_client):
    response = run_client.post("/run", json="just a string")
    assert response.status_code == 422


def test_run_ticket_returns_thread_and_reply(run_client):
    response = run_client.post(
        "/run",
        json={"ticket": "What is the customer return window?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"]
    assert len(body["thread_id"]) <= 255
    assert body["reply"]
    assert body["parked"] is False


def test_parked_refund_resumes_sqlite(tmp_path, monkeypatch):
    db = tmp_path / "ck.sqlite"
    monkeypatch.setenv("DATAFLOW_UI_MODEL", "fixture")
    monkeypatch.setenv("DATAFLOW_CHECKPOINTER", "sqlite")
    monkeypatch.setenv("DATAFLOW_SQLITE_PATH", str(db))
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "refunds.jsonl"))
    monkeypatch.setenv("DATAFLOW_HTTP_LOG", str(tmp_path / "http.jsonl"))
    monkeypatch.delenv("DATAFLOW_API_KEYS", raising=False)
    serve.reset_runtime()
    from fastapi.testclient import TestClient

    with TestClient(serve.app) as client:
        first = client.post(
            "/run",
            json={
                "ticket": "Please refund order DF-1001. The desk lamp is unused."
            },
        )
        assert first.status_code == 200
        body = first.json()
        assert body["parked"] is True
        tid = body["thread_id"]
        payload = body.get("payload") or {}
        assert payload.get("action") == "refund"
    serve.reset_runtime()
    with TestClient(serve.app) as client:
        again = client.post("/run", json={"thread_id": tid})
        assert again.status_code == 200
        parked = again.json()
        assert parked["parked"] is True
        assert parked["thread_id"] == tid
        assert (parked.get("payload") or {}).get("action") == "refund"
        assert Path(db).is_file()
