"""Pair C: the long task, run_session and the fold that never orphans a tool result. No model; a scripted one."""

import json
import re

from dataflow.context.agent import CUSTOMER_FILES, ContextAgent, compact_messages
from dataflow.context.long_task import INTRO, build_long_task, pass_lines, ticket_texts
from dataflow.context.rot import CONSTRAINT, FILLERS, PROBE
from dataflow.context.window_log import read_log


def test_the_long_task_is_sixty_turns_from_disk():
    turns = build_long_task(60, "C-2001")
    assert len(turns) == 60 and turns[3] == CONSTRAINT and turns[-1] == PROBE
    on_disk = set(INTRO) | set(FILLERS) | set(ticket_texts("C-2001")) | {PROBE}
    assert all(turn in on_disk for turn in turns)
    assert not any(re.search(r"\bC-\d{4}\b", turn) for turn in turns)
    assert {m for turn in turns for m in re.findall(r"DF-\d+", turn)} == {"DF-1001"}


def _tool_turns(n: int) -> list:
    messages = [{"role": "system", "content": "desk"}]
    for i in range(n):
        messages.append({"role": "user", "content": f"question {i} " + "policy " * 15})
        messages.append({"role": "assistant", "content": "", "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]})
        messages.append({"role": "tool", "tool_call_id": f"c{i}", "content": "file text " * 10})
        messages.append({"role": "assistant", "content": f"answer {i}"})
    return messages


def _paired(messages: list) -> bool:
    called = set()
    for m in messages:
        for call in m.get("tool_calls") or []:
            called.add(call["id"])
        if m.get("role") == "tool" and m.get("tool_call_id") not in called:
            return False
    return True


def test_compaction_never_orphans_a_tool_result():
    messages = _tool_turns(6)
    for keep_last in range(1, 12):
        new, folded, _b, _a = compact_messages(messages, threshold=50, keep_last=keep_last, summariser=lambda _t: "facts.")
        assert folded
        assert new[1]["content"].startswith("SUMMARY") and new[2]["role"] != "tool", keep_last
        assert _paired(new), keep_last


def scripted_desk(seen: list):
    def call(messages: list) -> dict:
        seen.append([dict(m) for m in messages])
        user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        answered = messages[-1]["role"] == "tool"
        if answered:
            return {"content": "Noted, here is what the file says.", "tool_calls": [], "usage": {"input_tokens": 100}}
        if user == CONSTRAINT:
            return {"content": "", "tool_calls": [{"id": "n1", "name": "write_note", "arguments": {"key": "constraint", "value": "Refunds never exceed 40 dollars."}}]}
        if "Approve the full amount" in user:
            capped = any("40 dollars" in str(m["content"]) and m["role"] == "system" for m in messages)
            return {"content": "Refunds on this account are capped at 40 dollars." if capped else "Approved, 49 dollars.", "tool_calls": []}
        if "return" in user.lower():
            return {"content": "", "tool_calls": [{"id": f"r{len(seen)}", "name": "read_file", "arguments": {"path": "return_policy.md"}}]}
        return {"content": "Happy to help with that question about your account today.", "tool_calls": [], "usage": {"input_tokens": 80}}

    return call


def test_the_long_task_holds_with_the_controls_on(tmp_path, monkeypatch):
    from dataflow.context import agent

    monkeypatch.setattr(agent, "CONTEXT_DIR", tmp_path)
    seen = []
    log = tmp_path / "w.jsonl"
    desk = ContextAgent(
        scripted_desk(seen),
        system="desk",
        customer_id="C-2001",
        allowed=CUSTOMER_FILES,
        guard=True,
        budget=1200,
        keep_last=6,
        stable_prefix=True,
        summariser=lambda _text: ("facts: a lamp order. actions: reads.", {"input_tokens": 90}),
        window_log=log,
        run_id="t",
    )
    result = desk.run_session(build_long_task(60, "C-2001"))
    rows = read_log(log)
    lines = pass_lines(result, rows, 1200, "C-2001")
    assert lines["turns"] == 60 and lines["stayed_under"] is True and lines["compactions"] > 0
    assert lines["cap_in_last_window"] == ["notes"]
    assert lines["other_customer_ids_in_window"] == []
    assert lines["verdict"] == "held"
    assert result["stop"] == "final" and "return_policy.md" in result["reads"]
    assert all(_paired(window) for window in seen)
    assert all("40" not in row["summary"] for row in result["token_trace"] if row.get("event") == "compact")
    assert len([row for row in result["token_trace"] if row.get("turn")]) == 60
    assert all("seconds" in row for row in result["token_trace"] if row.get("turn"))


def test_without_notes_the_fold_takes_the_rule_away(tmp_path):
    seen = []
    desk = ContextAgent(
        scripted_desk(seen),
        system="desk",
        budget=1200,
        keep_last=6,
        summariser=lambda _text: "facts: a lamp order.",
    )
    result = desk.run_session(build_long_task(60, "C-2001"))
    assert result["replies"][-1] == "Approved, 49 dollars."
    assert json.dumps(seen[-1]).count("40 dollars") == 0
