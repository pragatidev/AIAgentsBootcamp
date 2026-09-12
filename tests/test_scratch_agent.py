"""ScratchAgent. Scripted fixture model. No Ollama."""

from techcorp.agent.scratch import ScratchAgent, lookup_user, reset_password


def test_stops_on_final_answer():
    script = [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": "lookup_user",
                    "arguments": {"user_id": "E-4101"},
                    "arguments_json": '{"user_id": "E-4101"}',
                }
            ],
        },
        {"content": "Looked up E-4101. Password reset is ready.", "tool_calls": []},
    ]

    def call(_messages):
        return script.pop(0)

    agent = ScratchAgent(
        call,
        {"lookup_user": lookup_user, "reset_password": reset_password},
        cap=8,
    )
    out = agent.run("TC-1001 user E-4101 forgot the laptop password.")
    assert out["stop"] == "final"
    assert "E-4101" in out["final"]
    names = [row["name"] for row in out["rounds"] if row["kind"] == "tool"]
    assert names == ["lookup_user"]


def test_cap_stops_runaway():
    calls = {"n": 0}

    def call(_messages):
        calls["n"] += 1
        return {
            "content": "",
            "tool_calls": [
                {
                    "id": "spin",
                    "name": "nudge",
                    "arguments": {},
                    "arguments_json": "{}",
                }
            ],
        }

    agent = ScratchAgent(call, {"nudge": lambda: "try again"}, cap=3)
    out = agent.run("keep going")
    assert out["stop"] == "cap"
    assert calls["n"] == 3
    assert out["final"] == "desk could not finish"


def test_gate_refuses_write():
    def call(_messages):
        return {
            "content": "",
            "tool_calls": [
                {
                    "id": "r1",
                    "name": "reset_password",
                    "arguments": {"user_id": "E-4101"},
                    "arguments_json": '{"user_id": "E-4101"}',
                }
            ],
        }

    agent = ScratchAgent(
        call,
        {"reset_password": reset_password},
        cap=8,
        gate_writes=True,
        approve="no",
    )
    out = agent.run("reset the password for E-4101")
    assert out["stop"] == "gate"
    assert out["final"] == "write refused"
    tool_rows = [row for row in out["rounds"] if row["kind"] == "tool"]
    assert tool_rows == []
