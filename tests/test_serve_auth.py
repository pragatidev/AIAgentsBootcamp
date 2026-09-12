"""Auth and rate limit on POST /run. Fixture model. No Ollama."""

from __future__ import annotations

import pytest

from dataflow.ops import tracer
from dataflow.serve import app as serve


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAFLOW_UI_MODEL", "fixture")
    monkeypatch.setenv("DATAFLOW_CHECKPOINTER", "memory")
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "refunds.jsonl"))
    monkeypatch.setenv("DATAFLOW_HTTP_LOG", str(tmp_path / "http.jsonl"))
    monkeypatch.setenv("DATAFLOW_API_KEYS", "desk-key:reviewer-1,other-key:reviewer-2")
    monkeypatch.setenv("DATAFLOW_RATE_LIMIT", "3")
    monkeypatch.setenv("DATAFLOW_RATE_WINDOW_SEC", "60")
    monkeypatch.delenv("DATAFLOW_SKIP_API_KEY", raising=False)
    monkeypatch.delenv("DATAFLOW_RATE_LIMIT_OFF", raising=False)
    monkeypatch.delenv("DATAFLOW_SKIP_INTERRUPT", raising=False)
    serve.reset_runtime()
    serve.reset_rate_buckets()
    from fastapi.testclient import TestClient

    with TestClient(serve.app) as client:
        yield client


def test_401_without_key(auth_client):
    response = auth_client.post(
        "/run",
        json={"ticket": "Where is order DF-1002?"},
    )
    assert response.status_code == 401


def test_200_with_key(auth_client):
    response = auth_client.post(
        "/run",
        json={"ticket": "Where is order DF-1002?"},
        headers={"x-api-key": "desk-key"},
    )
    assert response.status_code == 200
    assert response.json()["thread_id"]


def test_actor_reaches_the_tool(auth_client):
    tracer.last_actor_line = None
    response = auth_client.post(
        "/run",
        json={"ticket": "Please refund order DF-1001. The desk lamp is unused."},
        headers={"x-api-key": "desk-key", "x-actor-id": "reviewer-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parked"] is True
    assert body["actor"] == "reviewer-1"
    line = tracer.last_actor_line or ""
    assert "actor=reviewer-1" in line


def test_429_after_cap_has_retry_after(auth_client):
    serve.reset_rate_buckets()
    headers = {"x-api-key": "desk-key"}
    codes = []
    retry_after = None
    for i in range(5):
        response = auth_client.post(
            "/run",
            json={"ticket": "Where is order DF-1002? n=" + str(i)},
            headers=headers,
        )
        codes.append(response.status_code)
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after") or response.headers.get(
                "Retry-After"
            )
    assert 200 in codes
    assert 429 in codes
    assert retry_after is not None
    assert int(retry_after) >= 1
