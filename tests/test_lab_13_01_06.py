"""Lab 13_01_06 (Lecture 28.8), mcp_tools typed by the student. A scripted model stands in for the real one here, and only here.

capfd, not capsys: the stdio server is a child process and needs a real stderr handle.
"""

import json
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from dataflow.mcp.server import PID_PATH
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_01_06_mcpadapter.py"
TARGET_LINE = "server_target = cfg\n"
# The desk asks lookup_order for DF-1002, then repeats what the server sent back.
SCRIPT = [AIMessage(content="", tool_calls=[{"name": "lookup_order", "args": {"order_id": "DF-1002"}, "id": "l", "type": "tool_call"}]), "echo_tool"]


@pytest.fixture
def run_lab(monkeypatch, capfd):
    def run(path: Path = LAB) -> list[str]:
        monkeypatch.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=list(SCRIPT)))
        runpy.run_path(str(path), run_name="__main__")
        return capfd.readouterr().out.splitlines()

    return run


def _metadata(out: list[str], name: str) -> dict:
    at = out.index("tool " + name)
    line = out[at + 2].strip()
    assert line.startswith("metadata_mcp ")
    return json.loads(line[len("metadata_mcp "):])


def test_the_adapter_lists_both_tools_with_their_hints(run_lab):
    out = run_lab()
    assert "tool lookup_order" in out and "tool refund" in out
    assert _metadata(out, "lookup_order")["tool"]["annotations"] == {"read_only_hint": True}
    assert _metadata(out, "refund")["tool"]["annotations"] == {"destructive_hint": True}
    assert _metadata(out, "lookup_order")["server"]["name"] == "dataflow"
    schema = json.loads(out[out.index("tool refund") + 1].strip()[len("args_schema "):])
    assert schema["required"] == ["order_id", "amount", "reason"]


def test_the_desk_calls_lookup_order_for_df_1002(run_lab):
    out = run_lab()
    assert "bound_names ['lookup_order', 'refund']" in out
    assert "tools_ran [('lookup_order', {'order_id': 'DF-1002'})]" in out
    reply = next(line for line in out if line.startswith("reply "))
    # The adapter hands the row back as a text content block; the scripted model repeats it.
    assert '"found":true,"order_id":"DF-1002","item":"USB-C hub","status":"in_transit"' in reply
    assert "pid_file_left False" in out
    assert not PID_PATH.is_file()


def test_a_bare_string_path_is_refused_with_value_error(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, TARGET_LINE, 'server_target = "dataflow/mcp/server.py"\n')
    out = run_lab(copy)
    refused = next(line for line in out if line.startswith("adapter_refused "))
    assert refused.startswith("adapter_refused ValueError MCP target 'dataflow/mcp/server.py'")
    assert not any(line.startswith("tool ") for line in out)
    assert "tools_ran [('lookup_order', {'order_id': 'DF-1002'})]" in out
