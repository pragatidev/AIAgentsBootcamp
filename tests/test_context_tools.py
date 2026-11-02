"""Part 3 context tools. Fixture models. No Ollama."""

from pathlib import Path

from dataflow.context.agent import (
    ContextAgent,
    compact_messages,
    count_tokens,
    read_file,
    write_note,
)
from dataflow.context.map_text import MAP, map_lines

ROOT = Path(__file__).resolve().parents[1]


def test_map_has_twelve_lines_with_when():
    lines = map_lines()
    assert len(lines) == 12
    for line in lines:
        assert " | " in line
        assert "when" in line.lower()


def test_every_map_entry_is_readable():
    from dataflow.context.map_text import check_map, load_map

    assert check_map(load_map()) == []


def test_check_map_names_an_unreadable_entry():
    from dataflow.context.map_text import check_map, load_map

    broken = load_map() + "refund_policy.md | when the customer asks for a refund\n"
    assert check_map(broken) == ["refund_policy.md: not readable"]
    assert check_map(load_map() + "return_policy.md\n") == ["return_policy.md: needs a name, a bar and a when"]


def test_load_map_reads_the_file(tmp_path):
    from dataflow.context.map_text import load_map

    path = tmp_path / "MAP.md"
    path.write_text("Role: test.\nMap:\nshipping.md | when asked about delivery\n", encoding="utf-8")
    assert load_map(path) == "Role: test.\nMap:\nshipping.md | when asked about delivery\n"
    assert map_lines(load_map(path)) == ["shipping.md | when asked about delivery"]


def test_chat_caller_passes_num_ctx(monkeypatch):
    import config
    from dataflow.context.agent import chat_caller

    seen = []
    monkeypatch.setattr(config, "get_local_chat_model", lambda **kw: seen.append(kw) or object())
    chat_caller(num_ctx=16384)
    chat_caller()
    assert seen[0]["num_ctx"] == 16384
    assert seen[0]["reasoning"] is False
    assert "num_ctx" not in seen[1]


def test_openai_caller_returns_usage(monkeypatch):
    import openai
    from openai.types.chat import ChatCompletion

    from dataflow.context.agent import _usage
    from techcorp.agent.scratch import openai_caller

    reply = ChatCompletion.model_validate(
        {
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": "qwen3:8b",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Thirty days."},
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 4,
                "total_tokens": 124,
                "prompt_tokens_details": {"cached_tokens": 100},
            },
        }
    )

    class FakeClient:
        def __init__(self, **_kw):
            self.chat = self
            self.completions = self

        def create(self, **_kw):
            return reply

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    out = openai_caller([])([{"role": "user", "content": "return window?"}])
    assert out["content"] == "Thirty days."
    assert out["usage"]["prompt_tokens"] == 120
    assert _usage(out) == {
        "input_tokens": 120,
        "output_tokens": 4,
        "total_tokens": 124,
        "cached_tokens": 100,
    }
    assert _usage({"usage": {"input_tokens": 7, "output_tokens": 1, "total_tokens": 8}})["input_tokens"] == 7


def test_judge_refund_reply():
    from dataflow.context.rot import judge_refund_reply

    # The turn-30 and turn-45 replies of the 2026-09-12 capture (lecture 5.2), word for word.
    turn_30 = (
        "The refund for order DF-1001 will be processed for $129, but it will not exceed $40 "
        "as per the account's refund policy."
    )
    turn_45 = (
        "Your refund request for order DF-1001 will be processed for $40, as refunds for this "
        "account must not exceed $40."
    )
    assert judge_refund_reply(turn_30) == "contradicted"
    assert judge_refund_reply(turn_45) == "held"
    assert judge_refund_reply("Approved, your 49 dollar refund is on its way.") == "broke"
    assert judge_refund_reply("I cannot refund 49 dollars; refunds here are capped at $40.") == "held"
    assert judge_refund_reply("Refunds are capped at 40 dollars.") == "held"
    assert judge_refund_reply("Let me check that order for you.") == "broke"


def test_probe_asks_for_the_lamps_own_price():
    import json

    from dataflow.context.rot import PROBE, PROBE_AMOUNT

    orders = json.loads((ROOT / "dataflow" / "data" / "orders.json").read_text(encoding="utf-8"))
    assert PROBE_AMOUNT == int(orders["DF-1001"]["amount"]) == 49
    assert "49 dollars" in PROBE and "129" not in PROBE


def test_pick_rows_on_a_known_trace():
    from dataflow.context.rot import pick_rows

    trace = [
        {"turn": 3, "tokens": 90},
        {"turn": 4, "tokens": 150},
        {"event": "compact", "tokens_before": 300, "tokens_after": 100},
        {"turn": 30, "tokens": 1300},
    ]
    rows = pick_rows(trace, 30)
    assert rows["before"]["tokens"] == 150
    assert rows["after"]["tokens"] == 1300
    assert pick_rows(trace)["after"]["turn"] == 30
    assert pick_rows([], None) == {"before": None, "after": None}


def test_compaction_folds_over_threshold():
    messages = [{"role": "system", "content": "desk"}]
    for i in range(20):
        messages.append({"role": "user", "content": f"turn {i} " + ("policy " * 20)})
        messages.append({"role": "assistant", "content": "ok " + str(i)})

    def summariser(text: str) -> str:
        return "facts: lamp. actions: none. decisions: none. open questions: none."

    before = count_tokens(messages)
    new, folded, n_before, n_after = compact_messages(
        messages,
        threshold=50,
        keep_last=4,
        summariser=summariser,
    )
    assert folded is True
    assert n_before == before
    assert n_after < n_before
    assert any("SUMMARY" in str(m.get("content")) for m in new)


def _long_messages(n: int = 20) -> list:
    messages = [{"role": "system", "content": "desk"}]
    for i in range(n):
        messages.append({"role": "user", "content": f"turn {i} " + ("policy " * 20)})
        messages.append({"role": "assistant", "content": "ok " + str(i)})
    return messages


def test_fold_keeps_the_system_message():
    new, folded, _before, _after = compact_messages(
        _long_messages(), threshold=50, keep_last=4, summariser=lambda _t: "facts: lamp."
    )
    assert folded is True
    assert new[0] == {"role": "system", "content": "desk"}
    assert new[1] == {"role": "assistant", "content": "SUMMARY\nfacts: lamp."}
    assert new[2:] == _long_messages()[-4:]


def test_fold_records_its_summary():
    def summariser(_text: str):
        return "facts: order DF-1001. actions: none.", {"input_tokens": 300, "output_tokens": 12}

    def call(_messages):
        return {"content": "ok " * 10, "tool_calls": [], "usage": {"input_tokens": 50}}

    agent = ContextAgent(call, system="desk", compact=True, compact_threshold=60, keep_last=2, summariser=summariser)
    out = agent.run_turns(["question about the lamp " * 3] * 6)
    folds = [row for row in out["token_trace"] if row.get("event") == "compact"]
    assert folds
    assert folds[-1]["summary"] == "SUMMARY\nfacts: order DF-1001. actions: none."
    assert folds[-1]["summariser_usage"] == {"input_tokens": 300, "output_tokens": 12}


def test_compaction_caps_the_last_call():
    from dataflow.context.agent import total_input

    def call(_messages):
        return {"content": "ok, noted for the desk lamp order", "tool_calls": [], "usage": {"input_tokens": 100}}

    def summariser(_text: str):
        return "facts: DF-1001.", {"input_tokens": 70}

    turns = ["Order DF-1001, the desk lamp."] + [f"question {i} about shipping and invoices" for i in range(14)]
    plain = ContextAgent(call, system="desk", compact=False).run_turns(turns)
    comp = ContextAgent(call, system="desk", compact=True, compact_threshold=120, keep_last=4, summariser=summariser).run_turns(turns)
    last_plain = [r for r in plain["token_trace"] if r.get("turn")][-1]["tokens"]
    last_comp = [r for r in comp["token_trace"] if r.get("turn")][-1]["tokens"]
    folds = sum(1 for r in comp["token_trace"] if r.get("event") == "compact")
    assert last_comp < last_plain
    assert folds > 0
    totals = total_input(comp["token_trace"])
    assert totals == {"desk": 100 * 15, "summariser": 70 * folds, "total": 100 * 15 + 70 * folds}
    assert total_input(plain["token_trace"]) == {"desk": 1500, "summariser": 0, "total": 1500}


def _notes_run(notes_path):
    """Eight turns, the cap said on turn 1, a forgetful summariser; returns the last call's messages."""
    calls = []

    def call(messages):
        calls.append([dict(m) for m in messages])
        return {"content": "ok", "tool_calls": []}

    agent = ContextAgent(
        call,
        system="desk",
        compact=True,
        compact_threshold=10,
        keep_last=2,
        summariser=lambda _text: "facts: none. actions: none. decisions: none. open questions: none.",
        notes_path=notes_path,
    )
    out = agent.run_turns(["My refunds are capped at 40 dollars."] + ["hello"] * 7)
    return out, calls[-1]


def test_notes_survive_compaction(tmp_path):
    notes_path = tmp_path / "notes.json"
    write_note("constraint", "cap is 40 dollars", path=notes_path)
    out, last = _notes_run(notes_path)
    summary = [m for m in last if str(m.get("content")).startswith("SUMMARY")]
    assert summary and "40" not in summary[0]["content"]
    assert last[0]["role"] == "system" and "cap is 40 dollars" in last[0]["content"]
    assert not any("40 dollars" in str(m.get("content")) for m in last[1:])
    assert out["notes"]["constraint"] == "cap is 40 dollars"


def test_no_notes_no_cap_in_window(tmp_path):
    _out, last = _notes_run(tmp_path / "absent.json")
    assert not any("40" in str(m.get("content")) for m in last)


def test_write_note_assigns_and_keeps_other_keys(tmp_path):
    import json

    path = tmp_path / "notes.json"
    write_note("customer", "C-2001", path=path)
    out = json.loads(write_note("order", "DF-1001", path=path))
    assert out == {"ok": True, "key": "order", "notes": {"customer": "C-2001", "order": "DF-1001"}}
    write_note("order", "DF-1002", path=path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"customer": "C-2001", "order": "DF-1002"}


def test_protected_key_is_not_overwritten(tmp_path):
    import json

    path = tmp_path / "notes.json"
    write_note("constraint", "Refunds never exceed 40 dollars.", path=path)
    before = path.read_bytes()
    out = json.loads(write_note("constraint", "Customer prefers email.", path=path))
    assert out == {"ok": False, "key": "constraint", "reason": "protected key, ask a person"}
    assert path.read_bytes() == before


def test_context_caller_binds_tools_on_the_local_model(monkeypatch):
    import config
    from langchain_core.messages import AIMessage

    from dataflow.context.agent import NOTE_SCHEMA, READ_SCHEMA, context_caller

    seen = {}

    class Model:
        def bind_tools(self, tools):
            seen["tools"] = tools
            return self

        def invoke(self, messages):
            seen["messages"] = messages
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_file", "args": {"path": "return_policy.md"}, "id": "c1", "type": "tool_call"}],
                usage_metadata={"input_tokens": 9, "output_tokens": 3, "total_tokens": 12},
            )

    monkeypatch.setattr(config, "get_local_chat_model", lambda **kw: seen.update(kw=kw) or Model())
    call = context_caller(num_ctx=8192)
    out = call([{"role": "user", "content": "return window?"}])
    assert seen["kw"]["num_ctx"] == 8192 and seen["tools"] == [READ_SCHEMA, NOTE_SCHEMA]
    assert call.tool_names == ["read_file", "write_note"]
    assert out["tool_calls"] == [{"id": "c1", "name": "read_file", "arguments": {"path": "return_policy.md"}}]
    assert out["raw_tool_calls"][0]["function"] == {"name": "read_file", "arguments": '{"path": "return_policy.md"}'}
    assert out["usage"]["input_tokens"] == 9


def _keyword_reader_model(messages):
    """Reads return_policy.md for a return ticket and shipping.md for a shipping ticket, once."""
    last = next(str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user")
    if any(m.get("role") == "tool" for m in messages):
        return {"content": "answered from the file", "tool_calls": []}
    name = "return_policy.md" if "return" in last.lower() else "shipping.md" if "shipping" in last.lower() else ""
    if not name:
        return {"content": "noted", "tool_calls": []}
    return {"content": "", "tool_calls": [{"id": "r1", "name": "read_file", "arguments": {"path": name}}]}


def test_jit_read_only_on_match(tmp_path):
    ret = ContextAgent(_keyword_reader_model, system="desk", cap=4).run("What is the return window?")
    ship = ContextAgent(_keyword_reader_model, system="desk", cap=4).run("How many business days is standard shipping?")
    other = ContextAgent(_keyword_reader_model, system="desk", cap=4).run("Do you have a status page?")
    assert ret["reads"] == ["return_policy.md"] and ret["tool_names"] == ["read_file"]
    assert ship["reads"] == ["shipping.md"]
    assert other["reads"] == [] and other["tool_names"] == []
    assert "30 days" in read_file("return_policy.md")
    tool_text = [m["content"] for m in ship["messages"] if m.get("role") == "tool"][0]
    assert '"found": true' in tool_text and "shipping.md" in tool_text


def test_read_file_refuses_outside_the_list():
    import json

    for path in ("../../.env", "..\\..\\.env", "/etc/passwd", "secrets.md", ""):
        out = json.loads(read_file(path))
        assert out["found"] is False and out["reason"] == "unknown file", path


def test_customer_files_refuse_the_handbook():
    import json

    from dataflow.context.agent import CUSTOMER_FILES

    assert json.loads(read_file("employee_handbook.txt"))["found"] is True
    refused = json.loads(read_file("employee_handbook.txt", allowed=CUSTOMER_FILES))
    assert refused == {"found": False, "path": "employee_handbook.txt", "reason": "not on this desk's list"}
    assert json.loads(read_file("competitive_analysis.txt", allowed=CUSTOMER_FILES))["found"] is False
    assert json.loads(read_file("return_policy.md", allowed=CUSTOMER_FILES))["found"] is True


def test_the_desk_uses_the_reader_it_is_given():
    seen = []
    desk = ContextAgent(_keyword_reader_model, system="desk", cap=4, reader=lambda path: seen.append(path) or '{"found": false}')
    desk.run("What is the return window?")
    assert seen == ["return_policy.md"]


def test_child_sees_only_its_document():
    docs = {
        "return_policy.md": "UNIQUE_RETURN_WINDOW_30",
        "employee_handbook.txt": "UNIQUE_EQUIPMENT_TERMINATION",
        "shipping.md": "UNIQUE_IN_TRANSIT_ONLY",
    }
    for name, body in docs.items():
        messages = [
            {"role": "system", "content": "Score this one document."},
            {"role": "user", "content": "FILE " + name + "\n" + body},
        ]
        blob = "\n".join(str(m.get("content")) for m in messages)
        for other, other_body in docs.items():
            if other == name:
                assert other_body in blob
            else:
                assert other_body not in blob


def test_a_desk_without_a_notes_file_never_reads_the_shared_one(tmp_path, monkeypatch):
    from dataflow.context import agent as agent_module

    shared = tmp_path / "notes.json"
    write_note("constraint", "cap is 40 dollars", path=shared)
    monkeypatch.setattr(agent_module, "NOTES_PATH", shared)
    sent = []
    desk = ContextAgent(lambda messages: sent.append(messages) or {"content": "ok", "tool_calls": []}, system="desk")
    desk.run_turns(["hello"])
    assert sent[0][0]["content"] == "desk"
