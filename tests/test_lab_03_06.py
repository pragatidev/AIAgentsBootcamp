"""Lab 03.06, run_desk typed by the student. A scripted model stands in for the real one here, and only here."""

import runpy
from pathlib import Path

import pytest

from dataflow.context import agent
from dataflow.context.agent import count_tokens
from dataflow.context.map_text import get_fat, load_map

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_06_fat_vs_map.py"
seen_windows = []


def scripted_chat_caller(num_predict: int = 80, num_ctx: int | None = None):
    seen_windows.append(num_ctx)

    def call(messages: list) -> dict:
        system = str(messages[0]["content"])
        answer = "Thirty days from delivery." if "30 days" in system else "Let me check the details for you."
        return {"content": answer, "tool_calls": [], "usage": {"input_tokens": len(system) // 4}}

    call.tool_names = []
    return call


@pytest.fixture
def run(monkeypatch):
    seen_windows.clear()
    monkeypatch.setattr(agent, "chat_caller", scripted_chat_caller)
    monkeypatch.setattr(agent, "applied_window", lambda: 16384)
    return lambda: runpy.run_path(str(LAB), run_name="__main__")


def test_run_desk_returns_both_counts_and_the_answer(run):
    lab = run()
    ticket = lab["TICKET"]
    library, server, answer = lab["run_desk"]("desk text", ticket, 2048)
    assert library == count_tokens([{"role": "system", "content": "desk text"}, {"role": "user", "content": ticket}])
    assert server == len("desk text") // 4
    assert answer == "Let me check the details for you."
    assert seen_windows[-1] == 2048


def test_both_desks_print_and_the_fat_desk_is_larger(capsys, run):
    run()
    out = capsys.readouterr().out.splitlines()
    value = {line.split(" ", 1)[0]: line.split(" ", 1)[1] for line in out}
    assert value["window"] == "16384"
    assert int(value["fat_library_tokens"]) > int(value["map_library_tokens"])
    assert int(value["fat_server_input_tokens"]) == len(get_fat()) // 4
    assert int(value["map_server_input_tokens"]) == len(load_map()) // 4
    assert value["fat_answer"] == "Thirty days from delivery."
    assert value["map_desk_tools"] == "[]"
    assert int(value["token_delta"]) == int(value["fat_library_tokens"]) - int(value["map_library_tokens"])
    assert set(seen_windows) == {16384}
