# %%
"""Lab 4.24: move the TechCorp agent into the package with tests.

What we build: the desk has lived in techcorp/agent/desk.py since lab 12, but no single function exists
that a service could call. You write that function, answer_ticket, the package keeps one copy of the
helper that reads the reply, and a test keeps the package honest. Then you break the package's main rule
on purpose and watch that test catch it.

What you learn: a package is importable, tested and configured, and nothing runs at import. You see what
breaking that rule costs as a number from a real model, and a test that fails before the desk tests get
going.

What will be true on your screen: the model's class and name, the reply to ticket TC-1002 and whether it
ends with the ticket id, the pytest summary line and its exit code, then how long one import takes when a
module calls the model at import.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from techcorp.agent.desk import build_techcorp_desk, reply_text, run_ticket


# %%
# TYPE THIS: answer_ticket. The signature and docstring are given; you type the body.
# Its finished copy is in techcorp/agent/desk.py.
def answer_ticket(text: str, user_id: str, *, model=None, thread_id: str | None = None) -> str:
    """The one call a service makes. Build the desk inside the call, never at import; run the ticket with
    the acting id in the envelope; return the reply as plain text, or say which write waits for a person."""
    desk = build_techcorp_desk(model=model)
    state = run_ticket(desk, text, user_id=user_id, thread_id=thread_id)
    if state.get("__interrupt__"):
        return "Waiting for a person to approve: " + state["__interrupt__"][0].value["action_requests"][0]["description"]
    return reply_text(state)


# BREAK: open techcorp/agent/desk.py and add this line under DEFAULT_TOOLS, the line a team adds to make
# the first ticket fast:
#     WARM_MODEL = get_chat_model()  # warm the model at import
# then run python -m pytest tests/test_lab_05_24.py -q and read the failure. Delete the line and run again.


def main() -> None:
    chat = config.get_chat_model()
    print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
    ticket = "Ticket TC-1002 for employee E-4102: VPN connects then drops every few minutes from the home office."
    reply = answer_ticket(ticket, "E-4102", model=chat).strip()
    print("reply", reply)
    print("reply_ends_with_ticket_id", reply.rstrip(".!) ").endswith("TC-1002"))

    tests = ["tests/test_techcorp_tools.py", "tests/test_techcorp_desk.py", "tests/test_lab_05_24.py"]
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=root, capture_output=True, text=True, encoding="utf-8")
    lines = done.stdout.strip().splitlines()
    print("pytest", lines[-1] if lines else done.stderr.strip()[-200:])
    print("exit_code", done.returncode)

    # What the broken rule costs: a module that calls the model when it is imported.
    plant_dir = Path(tempfile.mkdtemp())
    (plant_dir / "planted_model_at_import.py").write_text(
        "from config import get_chat_model\n\nREPLY = get_chat_model().invoke('ping from import')\n", encoding="utf-8"
    )
    sys.path.insert(0, str(plant_dir))
    started = time.perf_counter()
    import planted_model_at_import

    print("import_seconds", round(time.perf_counter() - started, 2))
    text = planted_model_at_import.REPLY.text.strip()
    print("import_reply_chars", len(text), "starts", text[:80].replace("\n", " "))


if __name__ == "__main__":
    main()
