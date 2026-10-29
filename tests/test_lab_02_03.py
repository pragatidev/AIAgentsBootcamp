"""Lab 02.03, the loop typed as a plain function. A scripted model stands in for Ollama here, and only here."""

import json
import runpy
from pathlib import Path

import pytest

import techcorp.agent.scratch as scratch

LAB = Path(__file__).resolve().parents[1] / "labs" / "02_03_scratch_agent.py"


def _reset_call(call_id: str) -> dict:
    args = {"user_id": "E-4101"}
    return {
        "content": "",
        "tool_calls": [
            {"id": call_id, "name": "reset_password", "arguments": args, "arguments_json": json.dumps(args)}
        ],
        "raw_tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": "reset_password", "arguments": json.dumps(args)},
            }
        ],
    }


def _two_step(_tools_schema):
    script = [
        _reset_call("c1"),
        {"content": "Done. Your temporary password is Tmp-4101.", "tool_calls": [], "raw_tool_calls": []},
    ]
    return lambda _messages: script.pop(0)


def _always_asks(_tools_schema):
    calls = iter(range(1, 1000))
    return lambda _messages: _reset_call(f"c{next(calls)}")


@pytest.fixture
def run_lab(monkeypatch, capsys):
    def run(model_factory, path: Path = LAB) -> list[str]:
        monkeypatch.setattr(scratch, "openai_caller", model_factory)
        runpy.run_path(str(path), run_name="__main__")
        return capsys.readouterr().out.splitlines()

    return run


def test_reset_then_answer_stops_final(run_lab):
    out = run_lab(_two_step)
    assert out[0] == "cap 8"
    assert out[1].startswith("ticket TC-1001 user E-4101")
    assert out[2] == 'round 1 tool reset_password {"user_id": "E-4101"}'
    result = json.loads(out[3].removeprefix("result "))
    assert result["reset"] is True and result["temp_password"] == "Tmp-4101"
    assert out[4] == "round 2 final Done. Your temporary password is Tmp-4101."
    assert out[-1] == "stop final"


def test_a_model_that_always_asks_stops_at_the_cap(run_lab):
    out = run_lab(_always_asks)
    tool_rounds = [line for line in out if line.startswith("round ") and " tool " in line]
    assert len(tool_rounds) == 8
    assert out[-2:] == ["final desk could not finish", "stop cap"]


def test_cap_is_one_constant_the_print_reads(run_lab, tmp_path):
    # The break in the lecture: edit CAP = 8 to CAP = 1. The printed cap and the loop both follow.
    text = LAB.read_text(encoding="utf-8")
    assert text.count("CAP = 8") == 1
    copy = tmp_path / "labs" / LAB.name
    copy.parent.mkdir()
    copy.write_text(text.replace("CAP = 8", "CAP = 1"), encoding="utf-8")
    out = run_lab(_always_asks, copy)
    assert out[0] == "cap 1"
    assert [line for line in out if line.startswith("round ")] == [
        'round 1 tool reset_password {"user_id": "E-4101"}'
    ]
    assert out[-2:] == ["final desk could not finish", "stop cap"]
