"""Lab 13_03_09 (Lecture 29.9), on_call_tool typed by the student: one audit line per MCP call.

No model is called. Tokens come from a test key pair; the server runs on a free local port, then in process.
"""

import asyncio
import json
import runpy
from pathlib import Path

import pytest
from fastmcp import Client

from dataflow.mcp.audit import AuditLog, read_audit
from dataflow.mcp.http import build_http_server
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_03_09_audit_log.py"
HEADERS_LINE = '            "headers": get_http_headers(),\n'


@pytest.fixture
def run_lab(monkeypatch, capsys):
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", "")

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


def _audit(out: list[str]) -> list[dict]:
    return [json.loads(line.split(" ", 1)[1]) for line in out if line.startswith("audit ")]


def test_one_line_per_call_with_caller_tool_outcome_and_trace(run_lab):
    lab, out = run_lab()
    assert "log_lines 4" in out
    rows = _audit(out)
    assert [(r["caller"], r["tool"], r["outcome"]) for r in rows] == [
        ("read_only_clerk", "lookup_order", "ok"),
        ("read_only_clerk", "refund", "refused: NotFoundError"),
        ("refund_clerk", "refund", "ok"),
        ("local", "lookup_order", "ok"),
    ]
    assert rows[0]["traceparent"] == lab["TRACEPARENT"] and rows[1]["traceparent"] is None
    assert rows[0]["headers"]["mcp-name"] == "lookup_order" and rows[3]["headers"] == {}
    assert all(isinstance(r["ms"], float) for r in rows)
    assert rows == read_audit(lab["log_path"])


def test_no_credential_and_no_free_text_reach_the_log(run_lab):
    lab, out = run_lab()
    assert "token_in_log False" in out and "reason_in_log False" in out
    text = lab["log_path"].read_text(encoding="utf-8")
    assert "authorization" not in text.lower() and "Bearer" not in text
    assert [r["args"].get("reason") for r in _audit(out) if r["tool"] == "refund"] == ["[redacted]", "[redacted]"]
    assert "server_stopped True" in out


def test_lab_audit_writes_what_the_package_writes(run_lab, tmp_path):
    lab, _ = run_lab()
    paths = {"lab": tmp_path / "lab.jsonl", "package": tmp_path / "package.jsonl"}

    async def one_call(middleware):
        async with Client(build_http_server(middleware=[middleware])) as client:
            await client.call_tool("lookup_order", {"order_id": "DF-1002"}, meta={"traceparent": "00-aa-bb-01"})

    asyncio.run(one_call(lab["LabAudit"](paths["lab"])))
    asyncio.run(one_call(AuditLog(paths["package"])))
    strip = lambda row: {k: v for k, v in row.items() if k not in ("time", "ms")}
    assert [strip(r) for r in read_audit(paths["lab"])] == [strip(r) for r in read_audit(paths["package"])]
    assert read_audit(paths["lab"])[0]["traceparent"] == "00-aa-bb-01"


def test_logging_the_whole_request_puts_the_bearer_token_in_the_file(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, HEADERS_LINE, '            "headers": get_http_headers(include_all=True),\n')
    lab, out = run_lab(copy)
    assert "token_in_log True" in out
    text = lab["log_path"].read_text(encoding="utf-8")
    for token in lab["tokens"].values():
        assert f"Bearer {token}" in text
