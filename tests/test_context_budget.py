"""Pair B: the budget as a control, the window log, the stable prefix, the map's owner. No model."""

from dataflow.context.agent import ContextAgent, _usage, count_tokens, write_note
from dataflow.context.map_text import MAP_PATH, check_map, load_map, map_header
from dataflow.context.window_log import read_log, sha256, source_of, where_in_window


def call(_messages):
    return {"content": "Noted, happy to help with that question today.", "tool_calls": [], "usage": {"input_tokens": 50, "output_tokens": 9, "total_tokens": 59}}


def summarise(_text):
    return "facts: DF-1001.", {"input_tokens": 70}


TURNS = ["Order DF-1001, the desk lamp."] + [f"Question {i} about shipping and invoices for my account." for i in range(20)]


def test_a_budget_below_the_system_prompt_stops_on_call_one(tmp_path):
    log = tmp_path / "w.jsonl"
    desk = ContextAgent(call, system=load_map(), budget=50, summariser=summarise, window_log=log)
    out = desk.run_turns(TURNS)
    assert out["stop"] == "budget" and out["replies"] == []
    assert read_log(log) == []
    stop = [r for r in out["token_trace"] if r.get("event") == "stop"][0]
    assert stop["budget"] == 50 and stop["tokens"] > 50
    refused = ContextAgent(call, system="desk", budget=50, on_over="refuse", summariser=summarise).run_turns(TURNS)
    assert refused["stop"] == "budget" and not any(r.get("event") == "compact" for r in refused["token_trace"])


def test_a_reachable_budget_never_logs_a_call_over_it(tmp_path):
    log = tmp_path / "w.jsonl"
    desk = ContextAgent(call, system="desk", budget=180, keep_last=4, summariser=summarise, window_log=log, run_id="t")
    out = desk.run_turns(TURNS)
    rows = read_log(log)
    assert out["stop"] == "final" and len(rows) == len(TURNS)
    assert all(r["window_tokens"] <= 180 for r in rows)
    assert any(r.get("reason") == "budget" for r in out["token_trace"] if r.get("event") == "compact")


def test_the_log_has_one_row_per_call_with_a_source_on_every_message(tmp_path):
    log = tmp_path / "w.jsonl"
    notes = tmp_path / "notes.json"
    write_note("constraint", "Refunds never exceed 40 dollars.", notes)
    desk = ContextAgent(call, system="desk", notes_path=notes, stable_prefix=True, window_log=log, run_id="r", map_version="2")
    desk.run_turns(TURNS[:3])
    rows = read_log(log)
    assert [r["request_id"] for r in rows] == ["r-001", "r-002", "r-003"]
    assert all(m["source"] in {"system", "notes", "user", "assistant"} for r in rows for m in r["messages"])
    assert [m["source"] for m in rows[0]["messages"]] == ["system", "notes", "user"]
    assert rows[-1]["map_version"] == "2" and rows[-1]["notes_keys"] == ["constraint"]
    assert rows[0]["tokens"] == {"total": 59, "input": 50, "output": 9}
    assert where_in_window(rows[-1], "40 DOLLARS") == ["notes"]
    assert rows[0]["window_tokens"] == count_tokens(desk.window([{"role": "system", "content": "desk"}, {"role": "user", "content": TURNS[0]}]))


def test_the_log_masks_secrets_and_tags_tool_reads(tmp_path):
    def reader_model(messages):
        if any(m.get("role") == "tool" for m in messages):
            return {"content": "done", "tool_calls": []}
        return {"content": "", "tool_calls": [{"id": "r1", "name": "read_file", "arguments": {"path": "shipping.md"}}]}

    log = tmp_path / "w.jsonl"
    ContextAgent(reader_model, system="desk", window_log=log).run("ship? key sk-abcdefghijklmnopqrstuvwx")
    rows = read_log(log)
    assert [m["source"] for m in rows[-1]["messages"]] == ["system", "user", "assistant", "tool:read_file:shipping.md"]
    assert "sk-" not in log.read_text(encoding="utf-8")
    assert source_of({"role": "assistant", "content": "SUMMARY\nx"}, 3) == "summary"


def test_the_prefix_is_constant_across_a_note_write_only_when_stable(tmp_path):
    for stable, kept in ((False, False), (True, True)):
        notes = tmp_path / f"notes_{stable}.json"
        desk = ContextAgent(call, system="desk", notes_path=notes, stable_prefix=stable)
        messages = [desk._first_message(), {"role": "user", "content": "hi"}]
        before = sha256(desk.window(messages)[0]["content"])
        write_note("preference", "Email only.", notes)
        after = sha256(desk.window(messages)[0]["content"])
        assert (before == after) is kept
        assert "Email only." in "".join(m["content"] for m in desk.window(messages))


def test_usage_reads_both_shapes():
    assert _usage({"usage": {"prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11}})["input_tokens"] == 9
    assert _usage({"usage": {"input_tokens": 9, "output_tokens": 2, "total_tokens": 11}})["output_tokens"] == 2


def test_check_map_refuses_a_map_with_no_owner_line(tmp_path):
    raw = MAP_PATH.read_text(encoding="utf-8")
    assert check_map(raw, require_owner=True) == []
    assert map_header()["owner"] and map_header()["version"]
    no_owner = "\n".join(line for line in raw.splitlines() if not line.startswith("owner:")) + "\n"
    assert check_map(no_owner, require_owner=True) == ["MAP.md: no owner line"]
    assert "owner:" not in load_map()
    path = tmp_path / "MAP.md"
    path.write_text(no_owner, encoding="utf-8")
    assert "owner" not in map_header(path)
