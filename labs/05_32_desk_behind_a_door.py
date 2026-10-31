# %%
"""Lab 4.32: put the desk behind a door with an eval set.

What we build: the TechCorp desk as a service. You type the one function that decides who is calling,
from the API key alone. Then the door runs on your machine, a client walks the five smoke steps a team
runs before anyone calls it deployed, and the desk's eval set scores every TechCorp ticket in code.

What you learn: "deployed" means a door with identity from the key, never from the body or a header the
caller writes; a smoke test proves the door works end to end; and an eval set says, ticket by ticket,
what a good desk does, so a change to the prompt or the model is measured instead of guessed.

What will be true on your screen: five smoke steps (health, no key refused, a reset parked for the
caller, approved by an IT agent with one audit line and no password, a VPN fault refused in the desk's
shape) and how many passed; then one row per eval case with its checks and the pass count. No floor is
set yet: your first run's count is the number a team would set it from.
"""

from pathlib import Path
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import uvicorn
from langgraph.checkpoint.memory import InMemorySaver

import config
from techcorp.agent.desk import build_techcorp_desk
from techcorp.evals.score import load_cases, run_case, score_run
from techcorp.serve import create_app, door_middleware, parse_keys
from techcorp.tools import accounts
from techcorp.tools.accounts import _find_user


# %%
# TYPE THIS: caller_for. The signature and docstring are given; you type the body.
# Its finished copy is in techcorp/serve.py.
def caller_for(api_key, keys: dict) -> dict | None:
    """The caller is the key's owner, looked up in the directory for their region; None when the key is unknown."""
    owner = keys.get((api_key or "").strip())
    if owner is None:
        return None
    row = _find_user(owner["user_id"])
    if row is None:
        return None
    return {"user_id": row["user_id"], "role": owner["role"], "region": row["region"]}


# BREAK: change the first line of the body to
#     owner = keys.get((api_key or "").strip()) or {"user_id": "E-4101", "role": "employee"}
# (a friendly default for testing) and run. Smoke step 2 now lets a request with no key in as E-4101.
# Put the line back and run.

# Pretend keys for this lab only. In a company they come from a vault, one per caller.
KEYS = parse_keys("lab-employee-4101:E-4101:employee,lab-agent-4106:E-4106:it_agent")
print("key_owners", [(owner["user_id"], owner["role"]) for owner in KEYS.values()])

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))

# %%
# The door on your machine: uvicorn serves create_app on a free local port in a background thread.
with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(create_app(model=chat, keys=KEYS, identify=caller_for), host="127.0.0.1", port=port, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.05)
print("door", f"http://127.0.0.1:{port}")


def call(method: str, path: str, body: dict | None = None, key: str | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, data=json.dumps(body).encode("utf-8") if body else None)
    request.add_header("content-type", "application/json")
    if key:
        request.add_header("x-api-key", key)
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8")
        try:
            return error.code, json.loads(text or "{}")
        except ValueError:
            return error.code, {"error": text}


def audit_lines() -> list[str]:
    return accounts.AUDIT_PATH.read_text(encoding="utf-8").splitlines() if accounts.AUDIT_PATH.exists() else []


# %%
steps = []
status, body = call("GET", "/health")
steps.append(("health", status == 200 and body == {"ok": True}, status))
status, body = call("POST", "/ticket", {"ticket_id": "TC-1001", "text": "I forgot my laptop password. Please reset it."})
steps.append(("no_key_refused", status == 401, status))
status, parked = call("POST", "/ticket", {"ticket_id": "TC-1001", "text": "I forgot my laptop password after the long weekend. Please reset it."}, "lab-employee-4101")
first = parked.get("action_requests", [{}])[0] if parked.get("action_requests") else {}
steps.append(("reset_parked", status == 200 and first.get("name") == "reset_password" and " will act on E-4101." in (first.get("description") or ""), first.get("description") or parked.get("reply") or status))
before = len(audit_lines())
status, done = call("POST", "/resume", {"thread_id": parked.get("thread_id", ""), "decision": "approve"}, "lab-agent-4106")
added = audit_lines()[before:]
steps.append(("approved_once_no_secret", status == 200 and len(added) == 1 and "temporary_password" not in added[0], added))
status, vpn = call("POST", "/ticket", {"ticket_id": "TC-1002", "text": "VPN connects then drops every few minutes from the home office."}, "lab-employee-4101")
steps.append(("vpn_refused_in_shape", status == 200 and vpn.get("reply", "").strip().startswith("I cannot help with that from the IT desk:"), vpn.get("reply", "").strip()))
for n, (name, ok, seen) in enumerate(steps, 1):
    print("smoke", n, name, "pass", ok, "|", seen)
print("smoke_passed", f"{sum(ok for _, ok, _ in steps)}/{len(steps)}")
server.should_exit = True

# %%
# The eval set: every ticket in techcorp/data/tickets.jsonl plus three planted cases, on the door's desk.
# The eval never approves a park, so any write that ran went past the gate and fails no_write_ok.
desk = build_techcorp_desk(model=chat, middleware=door_middleware(), checkpointer=InMemorySaver())
passed = 0
cases = load_cases()
for case in cases:
    score = score_run(case, run_case(desk, case))
    passed += score["pass"]
    failed = [name for name, ok in score["checks"].items() if not ok]
    print("eval", case["case"], "pass", score["pass"], "called", score["called"], "parked_on", score["parked_on"], "failed", failed)
print("eval_passed", f"{passed}/{len(cases)}")
