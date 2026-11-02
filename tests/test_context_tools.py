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
    assert "MAP" in open(
        ROOT / "labs" / "03_05_map_file.py", encoding="utf-8"
    ).read()


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


def test_notes_survive_compaction(tmp_path):
    notes_path = tmp_path / "notes.json"
    write_note("constraint", "cap is 40 dollars", path=notes_path)

    def summariser(_text: str) -> str:
        return "facts: none. actions: none. decisions: none. open questions: none."

    def call(_messages):
        return {"content": "ok", "tool_calls": []}

    agent = ContextAgent(
        call,
        system="desk",
        compact=True,
        compact_threshold=10,
        keep_last=2,
        summariser=summariser,
        notes_path=notes_path,
    )
    out = agent.run_turns(["hello"] * 8)
    assert "40" not in summariser("x")
    assert out["notes"]["constraint"] == "cap is 40 dollars"


def test_jit_read_only_on_match(tmp_path):
    def call(messages):
        last = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last = str(msg.get("content") or "")
                break
        already = any(m.get("role") == "tool" for m in messages)
        if "return" in last.lower() and not already:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "r1",
                        "name": "read_file",
                        "arguments": {"path": "return_policy.md"},
                        "arguments_json": '{"path": "return_policy.md"}',
                    }
                ],
            }
        return {"content": "noted", "tool_calls": []}

    agent = ContextAgent(call, system="desk", cap=4, notes_path=tmp_path / "n.json")
    ret = agent.run("What is the return window?")
    ship = ContextAgent(call, system="desk", cap=4, notes_path=tmp_path / "n.json").run(
        "How many business days is standard shipping?"
    )
    assert "read_file" in ret["tool_names"]
    assert ret["reads"] == ["return_policy.md"]
    assert ship["tool_names"] == []
    raw = read_file("return_policy.md")
    assert "30 days" in raw


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
