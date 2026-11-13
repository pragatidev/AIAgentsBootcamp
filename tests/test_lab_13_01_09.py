"""Lab 13_01_09 (Lecture 28.9), two_servers typed by the student: orders and kb on one desk, and the refund gate's names.

A scripted model stands in for the real one here, and only here; retrieval inside the kb child is the
fixed passage from tests/fixtures/mcp_fixtures.py. capfd, not capsys: the stdio children need a real stderr.
"""

import importlib
import json
import runpy
from pathlib import Path

import pytest
from fastmcp import Client
from langchain_core.messages import AIMessage

import config
from dataflow.mcp.kb_server import kb
from dataflow.mcp.runtime import run_async
from dataflow.mcp.server import PID_PATH
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.lab_copy import lab_copy
from tests.fixtures.mcp_fixtures import PASSAGE, fake_retrieval_in_children

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_01_09_two_servers.py"
GATED = '        gated = [name for name in names if name == "refund" or name.endswith("_refund")]\n'
RT = importlib.import_module("dataflow.tools.retrieve")


def _call(name, args, cid):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid, "type": "tool_call"}])


SCRIPT = [
    _call("orders_lookup_order", {"order_id": "DF-1002"}, "o"),
    "echo_tool",
    _call("kb_retrieve", {"question": "How many days do I have to return an item?"}, "k"),
    "echo_tool",
]


@pytest.fixture
def run_lab(monkeypatch, capfd, tmp_path):
    fake_retrieval_in_children(tmp_path, monkeypatch)

    def run(path: Path = LAB) -> list[str]:
        monkeypatch.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=list(SCRIPT)))
        lab = runpy.run_path(str(path), run_name="__main__")
        out = capfd.readouterr().out.splitlines()
        return out, Path(lab["ledger"].name)

    return run


def _ledger_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def test_kb_server_retrieve_calls_retrieve_passages_in_the_customer_scope(monkeypatch):
    seen = []
    monkeypatch.setattr(RT, "retrieve_passages", lambda question, **kwargs: seen.append((question, kwargs)) or [PASSAGE])

    async def go():
        async with Client(kb) as client:
            tools = await client.list_tools()
            result = await client.call_tool("retrieve", {"question": "return window?"})
            return tools, result

    tools, result = run_async(go())
    assert [t.name for t in tools] == ["retrieve"]
    assert tools[0].description == RT.RETRIEVE_DESCRIPTION
    assert tools[0].annotations.read_only_hint is True
    assert result.data == [PASSAGE]
    assert seen == [("return window?", {"k": 3, "scope": "customer"})]


def test_three_prefixed_names_each_on_its_own_server(run_lab):
    out, _ = run_lab()
    assert "bound_names ['orders_lookup_order', 'orders_refund', 'kb_retrieve']" in out
    assert "protocol_versions {'orders': '2026-07-28', 'kb': '2026-07-28'}" in out
    assert "served_by {'orders_lookup_order': 'dataflow', 'orders_refund': 'dataflow', 'kb_retrieve': 'kb'}" in out


def test_each_question_reaches_its_server(run_lab):
    out, _ = run_lab()
    at = out.index("question Where is order DF-1002?")
    assert out[at + 1] == "  tools_ran [('orders_lookup_order', {'order_id': 'DF-1002'})]"
    assert '"order_id":"DF-1002","item":"USB-C hub"' in out[at + 2]
    at = out.index("question How many days do I have to return an item?")
    assert out[at + 1] == "  tools_ran [('kb_retrieve', {'question': 'How many days do I have to return an item?'})]"
    assert "The customer return window is 30 days from delivery." in out[at + 2]


def test_the_gate_built_from_the_bound_names_parks_the_refund(run_lab):
    out, ledger = run_lab()
    assert "gated ['orders_refund']" in out
    assert "refund_parked True" in out and "parked_on ['orders_refund']" in out
    assert "ledger_rows_before_decision 0" in out
    assert "ledger_rows_after_approve 1" in out
    rows = _ledger_rows(ledger)
    assert len(rows) == 1 and rows[0]["order_id"] == "DF-1001" and rows[0]["amount"] == 49.0
    assert "pid_file_left False" in out
    assert not PID_PATH.is_file()


def test_a_gate_on_the_bare_name_lets_the_refund_write(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, GATED, '        gated = ["refund"]\n')
    out, ledger = run_lab(copy)
    assert "gated ['refund']" in out
    assert "refund_parked False" in out
    assert "ledger_rows_before_decision 1" in out
    assert len(_ledger_rows(ledger)) == 1
