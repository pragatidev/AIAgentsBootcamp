# %%
"""Lab 4.26: portfolio, TechCorp IT desk v1 with README.

What we build: you finish the TechCorp desk as something you can show: one function that runs a ticket
through the human gate, and a README a hiring manager can follow from clone to green tests, with the
decisions you made and the limits you know about written down.

What you learn: create_agent is enough for this desk, and its honest limits go in the README instead of
a wish list. A README is a contract a test can check, the same way the desk is.

What will be true on your screen: the shipped desk's gate and its four choices; the reset ticket parked,
what it will act on, approved, and a reply that carries the temporary password; the VPN and monitor
tickets and whether each came back in the refusal shape; the audit lines this run added, read from the
file; and the pytest summary line with its exit code.
"""

from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.types import Command

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import DEFAULT_MIDDLEWARE, build_techcorp_desk, reply_text, run_ticket
from techcorp.tools import accounts


# %%
# TYPE THIS: handle_ticket. The signature and docstring are given; you type the body.
# Its finished copy is in techcorp/agent/desk.py.
def handle_ticket(desk, text: str, *, user_id: str, thread_id: str, decision: dict | None = None, approver: str | None = None) -> dict:
    """Run one ticket with the acting id in the envelope. If the human gate parks it, keep the action
    requests, and resume with `decision` when one is given. Return parked, action_requests and the reply."""
    request_id = uuid4().hex
    state = run_ticket(desk, text, user_id=user_id, thread_id=thread_id, request_id=request_id)
    parked = state.get("__interrupt__") or []
    requests = parked[0].value["action_requests"] if parked else []
    if parked and decision is not None:
        state = desk.invoke(
            Command(resume=decision),
            config={"configurable": {"thread_id": thread_id}},
            context=DeskContext(user_id=user_id, approver=approver, request_id=request_id),
        )
    return {"parked": bool(parked), "action_requests": requests, "reply": reply_text(state)}


REFUSAL = "I cannot help with that from the IT desk:"
TESTS = ["tests/test_techcorp_tools.py", "tests/test_techcorp_desk.py", "tests/test_lab_05_24.py", "tests/test_lab_05_26.py", "tests/test_techcorp_readme.py"]


def audit_lines() -> list[str]:
    path = accounts.AUDIT_PATH
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def main() -> None:
    chat = config.get_chat_model()
    print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
    # The desk as the package ships it: no middleware argument means the gate is on.
    desk = build_techcorp_desk(model=chat)
    for name, rule in DEFAULT_MIDDLEWARE[0].interrupt_on.items():
        print("gated", name, rule["allowed_decisions"])
    before = len(audit_lines())

    reset = handle_ticket(
        desk,
        "Ticket TC-1001 for employee E-4101: I forgot my laptop password after the long weekend. Please reset it.",
        user_id="E-4101",
        thread_id="lab-4-26-reset",
        decision={"decisions": [{"type": "approve"}]},
    )
    print("reset_parked", reset["parked"])
    for request in reset["action_requests"]:
        print("reset_action", request["name"], "|", request["description"])
    print("reset_reply", reset["reply"].strip())
    print("reset_reply_has_token", bool(re.search(r"\b[0-9a-f]{10}\b", reset["reply"])))

    vpn = handle_ticket(desk, "Ticket TC-1002 for employee E-4102: VPN connects then drops every few minutes from the home office.", user_id="E-4102", thread_id="lab-4-26-vpn")
    print("vpn_reply", vpn["reply"].strip())
    print("vpn_refused_in_shape", vpn["reply"].strip().startswith(REFUSAL))
    # TC-1099 is a ticket written for this lab: something the desk does not do.
    monitor = handle_ticket(desk, "Ticket TC-1099 for employee E-4101: I need a new 27 inch monitor for my desk.", user_id="E-4101", thread_id="lab-4-26-monitor")
    print("oos_reply", monitor["reply"].strip())
    print("oos_refused_in_shape", monitor["reply"].strip().startswith(REFUSAL))

    added = audit_lines()[before:]
    print("audit_lines_added", len(added))
    for line in added:
        print("audit_line", line)

    done = subprocess.run([sys.executable, "-m", "pytest", "-q", *TESTS], cwd=root, capture_output=True, text=True, encoding="utf-8")
    lines = done.stdout.strip().splitlines()
    print("pytest", lines[-1] if lines else done.stderr.strip()[-200:])
    print("exit_code", done.returncode)


if __name__ == "__main__":
    main()
