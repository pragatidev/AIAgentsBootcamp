"""15.2 sandboxed coding loop. Pytest stays green with no live model."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from techcorp.harness.sandboxed_loop import (
    SANDBOX,
    STOPPED,
    run_loop,
    run_tests_in_root,
)
from tests.fixtures.fake_model import ScriptedToolChatModel

FIXED = (
    '"""Tiny sandbox function the coding loop edits."""\n'
    "\n"
    "\n"
    "def add(a: int, b: int) -> int:\n"
    "    return a + b\n"
)

BROKEN = (
    '"""Tiny sandbox function the coding loop edits."""\n'
    "\n"
    "\n"
    "def add(a: int, b: int) -> int:\n"
    "    return a - b\n"
)

TEST_SRC = "from fixture import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"


def _tool_payloads(state: dict) -> list[dict]:
    rows = []
    for msg in state.get("messages") or []:
        kind = str(getattr(msg, "type", "") or msg.__class__.__name__).lower()
        if "tool" not in kind or "call" in kind:
            continue
        raw = getattr(msg, "content", "") or ""
        try:
            rows.append(json.loads(raw))
        except Exception:
            rows.append({"raw": raw})
    return rows


def test_write_outside_root_is_blocked():
    model = ScriptedToolChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "path": "../../README.md",
                            "content": "pwned by the sandbox test",
                        },
                        "id": "call_escape",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="stopped"),
        ]
    )
    out = run_loop(
        "write ../../README.md",
        model=model,
        root=SANDBOX,
        max_steps=4,
    )
    payloads = _tool_payloads(out)
    assert payloads
    miss = payloads[0]
    assert miss.get("denied") is True
    assert miss.get("reason") == "path is outside the sandbox root"
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "pwned by the sandbox test" not in text


def test_scripted_fix_makes_sandbox_test_pass(tmp_path):
    box = tmp_path / "sandbox"
    box.mkdir()
    (box / "fixture.py").write_text(BROKEN, encoding="utf-8")
    (box / "test_fixture.py").write_text(TEST_SRC, encoding="utf-8")
    (box / "notes.md").write_text("notes\n", encoding="utf-8")
    assert run_tests_in_root(box)["passed"] is False
    model = ScriptedToolChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {"path": "fixture.py", "content": FIXED},
                        "id": "call_fix",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "run_tests",
                        "args": {},
                        "id": "call_tests",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="the test passes"),
        ]
    )
    out = run_loop("fix fixture.py so test_add passes", model=model, root=box)
    payloads = _tool_payloads(out)
    writes = [row for row in payloads if row.get("wrote")]
    tests = [row for row in payloads if "passed" in row]
    assert writes
    assert tests
    assert tests[-1]["passed"] is True
    assert run_tests_in_root(box)["passed"] is True


def test_cap_stops_a_looping_script():
    calls = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "read_file",
                    "args": {"path": "notes.md"},
                    "id": f"call_read_{i}",
                    "type": "tool_call",
                }
            ],
        )
        for i in range(10)
    ]
    model = ScriptedToolChatModel(script=calls)
    out = run_loop("loop on notes.md", model=model, root=SANDBOX, max_steps=3)
    assert out["stopped"] == "cap"
    assert out["steps"] == 3
    assert STOPPED in str(getattr(out["messages"][-1], "content", ""))
