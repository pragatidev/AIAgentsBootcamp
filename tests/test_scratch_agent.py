"""run_loop and ScratchAgent. Scripted fixture model. No Ollama."""

from techcorp.agent.scratch import ScratchAgent, lookup_user, reset_password, run_loop


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

    out = run_loop(
        call,
        {"lookup_user": lookup_user, "reset_password": reset_password},
        "TC-1001 user E-4101 forgot the laptop password.",
        cap=8,
    )
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

    out = run_loop(call, {"nudge": lambda: "try again"}, "keep going", cap=3)
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

    out = run_loop(
        call,
        {"reset_password": reset_password},
        "reset the password for E-4101",
        cap=8,
        gate_writes=True,
        approve="no",
    )
    assert out["stop"] == "gate"
    assert out["final"] == "write refused"
    tool_rows = [row for row in out["rounds"] if row["kind"] == "tool"]
    assert tool_rows == []


def test_gate_yes_runs_write():
    # Lab 3.6's restore: the same gate, and the person says yes.
    script = [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "r1",
                    "name": "reset_password",
                    "arguments": {"user_id": "E-4101"},
                    "arguments_json": '{"user_id": "E-4101"}',
                }
            ],
        },
        {"content": "Reset done. Your temporary password is Tmp-4101.", "tool_calls": []},
    ]
    asked = []

    def approve(name, args):
        asked.append((name, args))
        return " Yes "

    out = run_loop(
        lambda _messages: script.pop(0),
        {"reset_password": reset_password},
        "reset the password for E-4101",
        cap=8,
        gate_writes=True,
        approve=approve,
    )
    assert asked == [("reset_password", {"user_id": "E-4101"})]
    tool_rows = [row for row in out["rounds"] if row["kind"] == "tool"]
    assert [row["name"] for row in tool_rows] == ["reset_password"]
    assert '"reset": true' in tool_rows[0]["result"]
    assert out["stop"] == "final"


def test_unknown_tool_becomes_a_result():
    # Lab 3.4's break: the model is told about lookup_user, the dict the loop runs is not.
    script = [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "l1",
                    "name": "lookup_user",
                    "arguments": {"user_id": "E-4102"},
                    "arguments_json": '{"user_id": "E-4102"}',
                }
            ],
        },
        {"content": "I could not look that account up.", "tool_calls": []},
    ]
    seen = []

    def call(messages):
        seen.append(list(messages))
        return script.pop(0)

    out = run_loop(call, {"reset_password": reset_password}, "TC-1002 user E-4102: what is on this account?")
    tool_rows = [row for row in out["rounds"] if row["kind"] == "tool"]
    assert len(tool_rows) == 1
    assert '"unknown tool"' in tool_rows[0]["result"]
    assert '"lookup_user"' in tool_rows[0]["result"]
    assert seen[1][-1] == {"role": "tool", "tool_call_id": "l1", "content": tool_rows[0]["result"]}
    assert out["stop"] == "final"


def test_bad_arguments_become_a_result():
    # The model names the right tool under the wrong key. The loop hands that back instead of a traceback.
    script = [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "b1",
                    "name": "reset_password",
                    "arguments": {"employee_id": "E-4101"},
                    "arguments_json": '{"employee_id": "E-4101"}',
                }
            ],
        },
        {"content": "I need the user id to reset it.", "tool_calls": []},
    ]

    out = run_loop(
        lambda _messages: script.pop(0),
        {"reset_password": reset_password},
        "TC-1001 user E-4101: please reset my laptop password.",
    )
    tool_rows = [row for row in out["rounds"] if row["kind"] == "tool"]
    assert len(tool_rows) == 1
    assert '"bad arguments"' in tool_rows[0]["result"]
    assert '"employee_id"' in tool_rows[0]["result"]
    assert out["stop"] == "final"


def test_class_runs_the_same_loop():
    def scripted():
        script = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "r1",
                        "name": "reset_password",
                        "arguments": {"user_id": "E-4101"},
                        "arguments_json": '{"user_id": "E-4101"}',
                    }
                ],
            },
            {"content": "Reset done. Your temporary password is Tmp-4101.", "tool_calls": []},
        ]
        return lambda _messages: script.pop(0)

    tools = {"reset_password": reset_password}
    ticket = "TC-1001 user E-4101: please reset my laptop password."
    by_function = run_loop(scripted(), tools, ticket, cap=8)
    agent = ScratchAgent(scripted(), tools, cap=8)
    by_class = agent.run(ticket)
    assert by_class["stop"] == by_function["stop"] == "final"
    assert by_class["final"] == by_function["final"]
    assert [r["kind"] for r in by_class["rounds"]] == [r["kind"] for r in by_function["rounds"]]
    assert agent.rounds == by_class["rounds"]
