"""Lab 05.22, TokenCounter.on_llm_end typed by the student. A scripted model stands in for the real one here, and only here."""

import runpy
from pathlib import Path

import pytest
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage

import config
from techcorp.agent.desk import build_techcorp_desk
from techcorp.agent.usage import TokenCounter
from techcorp.tools import accounts
from tests.fixtures.fake_model import ScriptedToolChatModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_22_stream_reply.py"
META = {"model_name": "scripted"}
USAGE = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


def _script() -> list:
    reset = {"name": "reset_password", "args": {"user_id": "E-4101"}, "id": "c1", "type": "tool_call"}
    return [
        AIMessage(content="", tool_calls=[reset], usage_metadata=USAGE, response_metadata=META),
        AIMessage(content="Your password is reset. TC-1001", usage_metadata=USAGE, response_metadata=META),
    ]


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(accounts, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: ScriptedToolChatModel(script=_script()))

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


def test_one_run_two_calls_thirty_tokens(run_lab):
    _, out = run_lab()
    assert "token_count 30 input 20 output 10 calls 2" in out
    import ast

    builtin = ast.literal_eval([line for line in out if line.startswith("builtin ")][0].removeprefix("builtin "))
    assert builtin == {"scripted": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30}}


def test_updates_show_model_gate_tools_model(run_lab):
    _, out = run_lab()
    nodes = [line.split()[1] for line in out if line.startswith("update ")]
    assert nodes == [
        "model", "ToolCallLimitMiddleware.after_model", "__interrupt__",
        "HumanInTheLoopMiddleware.after_model", "tools", "model",
        "ToolCallLimitMiddleware.after_model", "HumanInTheLoopMiddleware.after_model",
    ]
    assert "" not in out
    assert any(line.startswith("reply Your password is reset. TC-1001") for line in out)


def test_typed_counter_agrees_with_package_and_builtin(run_lab):
    lab, _ = run_lab()
    counters = [lab["TokenCounter"](), TokenCounter(), UsageMetadataCallbackHandler()]
    desk = build_techcorp_desk(model=ScriptedToolChatModel(script=_script()), middleware=[])
    desk.invoke({"messages": [HumanMessage(content="Ticket TC-1001: reset it.")]}, config={"callbacks": counters}, context=None)
    assert counters[0].total_tokens == counters[1].total_tokens == counters[2].usage_metadata["scripted"]["total_tokens"] == 30
    assert counters[0].calls == counters[1].calls == 2


def test_the_wrong_hook_counts_nothing(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, "    def on_llm_end(self, response, **kwargs) -> None:", "    def on_chat_model_end(self, response, **kwargs) -> None:")
    _, out = run_lab(copy)
    assert "token_count 0 input 0 output 0 calls 0" in out
