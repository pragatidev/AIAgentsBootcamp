"""Lab 03.08, compact typed by the student, against the shipped fold. A scripted model and summariser stand in for the real ones here, and only here."""

import runpy
from pathlib import Path

import pytest

from dataflow.context import agent
from dataflow.context.agent import compact_messages, count_tokens

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_08_compaction.py"
prompts = []


def scripted_chat_caller(num_predict: int = 80, num_ctx: int | None = None):
    def call(messages: list) -> dict:
        seen = " ".join(str(m.get("content")) for m in messages)
        if "Which order" in str(messages[-1]["content"]):
            text = "Order DF-1001; I will email you." if "DF-1001" in seen and "email" in seen else "I do not know."
        else:
            text = "Noted, happy to help with that."
        return {"content": text, "tool_calls": [], "usage": {"input_tokens": count_tokens(messages)}}

    call.tool_names = []
    return call


def scripted_summary(text: str, prompt: str = agent.SUMMARIZE_PROMPT):
    prompts.append(prompt)
    keep = [w for w in ("DF-1001", "email") if w in text]
    return "facts: " + ", ".join(keep) + ". actions: none. decisions: none. open questions: none.", {"input_tokens": len(text) // 4}


@pytest.fixture
def run(monkeypatch):
    prompts.clear()
    monkeypatch.setattr(agent, "chat_caller", scripted_chat_caller)
    monkeypatch.setattr(agent, "summarise_with_usage", scripted_summary)
    monkeypatch.setattr(agent, "applied_window", lambda: None)
    return lambda: runpy.run_path(str(LAB), run_name="__main__")


def long_messages() -> list:
    messages = [{"role": "system", "content": "desk"}]
    for i in range(20):
        messages.append({"role": "user", "content": f"turn {i} " + ("policy " * 20)})
        messages.append({"role": "assistant", "content": "ok " + str(i)})
    return messages


@pytest.mark.parametrize("which", ["module", "lab"])
def test_compaction_folds_over_threshold(run, which):
    fold = compact_messages if which == "module" else run()["compact"]

    def summariser(_text: str) -> str:
        return "facts: lamp. actions: none. decisions: none. open questions: none."

    messages = long_messages()
    new, folded, before, after = fold(messages, threshold=50, keep_last=4, summariser=summariser)
    assert (folded, before) == (True, count_tokens(messages))
    assert after < before and after == count_tokens(new)
    assert new[0]["role"] == "system" and new[1]["content"].startswith("SUMMARY\n") and new[2:] == messages[-4:]
    same, folded, b, a = fold(messages[:3], threshold=10_000, keep_last=4, summariser=summariser)
    assert (same, folded, b) == (messages[:3], False, a)


def test_the_lab_runs_your_fold_and_prints_the_summary(capsys, run):
    lab = run()
    out = capsys.readouterr().out.splitlines()
    assert lab["agent"].compactor is lab["compact"]
    assert "threshold 180" in out and "keep_last_messages 4" in out
    folds = int(next(line for line in out if line.startswith("compactions ")).split()[1])
    assert folds > 0 and len([line for line in out if line.startswith("compact before")]) == folds
    assert next(line for line in out if line.startswith("last_summary ")).startswith("last_summary SUMMARY")
    assert out[-1] == "probe_reply Order DF-1001; I will email you."
    assert set(prompts) == {agent.SUMMARIZE_PROMPT}
