"""Lab 13_03_04 (Lecture 29.4), TOOL_SCOPES and scoped_server typed by the student: one scope per tool.

No model is called. Tokens come from a test key pair; the server runs on a free local port.
"""

import json
import runpy
from pathlib import Path

import pytest

from dataflow.mcp.http import TOOL_SCOPES as PACKAGE_SCOPES, build_http_server
from dataflow.mcp.runtime import run_async
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_03_04_scopes.py"
REFUND_SCOPE = '    "refund": "orders:refund",\n'


@pytest.fixture
def run_lab(monkeypatch, capsys):
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", "")

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


def _rows(lab) -> list[dict]:
    text = Path(lab["ledger"].name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _scopes_of(server) -> dict:
    """Each tool's required scopes, read from the server's own registry (a client with no token sees no scoped tool)."""

    async def go():
        tools = await server.local_provider.list_tools()
        return {tool.name: sorted(tool.auth.required_scopes) for tool in tools}

    return run_async(go())


def test_the_read_only_clerk_sees_the_lookup_only_and_cannot_refund(run_lab):
    lab, out = run_lab()
    assert "read_only_clerk sees ['lookup_order']" in out
    assert "read_only_clerk refund_refused ToolError Unknown tool: 'refund'" in out
    assert "read_only_clerk ledger_rows_added 0" in out
    assert "wire status 200" in out and "wire isError True" in out and "wire text Unknown tool: 'refund'" in out


def test_the_refund_clerk_sees_both_and_the_refund_writes_once(run_lab):
    lab, out = run_lab()
    assert "refund_clerk sees ['lookup_order', 'refund']" in out
    assert "refund_clerk ledger_rows_added 1" in out
    rows = _rows(lab)
    assert len(rows) == 1 and rows[0]["order_id"] == "DF-1001" and rows[0]["amount"] == 49.0
    assert "server_stopped True" in out


def test_lab_scopes_match_the_package(run_lab):
    lab, _ = run_lab()
    assert lab["TOOL_SCOPES"] == PACKAGE_SCOPES
    package = build_http_server(scopes=PACKAGE_SCOPES)
    student = lab["scoped_server"](lab["TOOL_SCOPES"], None)
    assert _scopes_of(student) == _scopes_of(package) == {"lookup_order": ["orders:read"], "refund": ["orders:refund"]}


def test_a_refund_filed_under_orders_read_lets_the_read_only_clerk_refund(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, REFUND_SCOPE, '    "refund": "orders:read",\n')
    lab, out = run_lab(copy)
    assert "read_only_clerk sees ['lookup_order', 'refund']" in out
    assert any(line.startswith("read_only_clerk refund {") for line in out)
    assert "read_only_clerk ledger_rows_added 1" in out
    # the clerks' two refunds, and the read-only token's refund sent by hand on the wire
    assert "wire isError False" in out
    assert len(_rows(lab)) == 3
