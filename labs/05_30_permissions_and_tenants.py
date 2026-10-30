# %%
"""Lab 4.30: permissions and tenants on the desk.

What we build: the desk's own rule table, who may call which tool, kept as data, and the function you
type that checks a proposed call against it using only the request envelope. A middleware applies it to
every call before a person or a tool sees it. Then the grant ticket runs three ways and a request with
no envelope id runs once.

What you learn: permissions come from the envelope the caller's system fills, never from the model's
text, so a ticket that claims a role cannot raise it. Region is this desk's tenant: one region's desk
does not touch another region's employees. A real multi-tenant desk also splits storage, keys and logs;
this one splits only the rule.

What will be true on your screen: the rules and the share list; four decisions from your function before
any model runs; then on the real desk, the employee's grant refused for the role, the EU IT agent's grant
allowed and parked for a person, the US IT agent's grant refused for the region, and the empty envelope's
reset refused, each refusal before anything parks.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.checkpoint.memory import InMemorySaver

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk, reply_text, run_ticket, write_gate
from techcorp.agent.middleware import PermissionGate, region_prompt
from techcorp.agent.permissions import RULES, SHARES
from techcorp.tools.accounts import _find_user

print("rules", json.dumps(RULES))
print("shares", json.dumps(SHARES))


# %%
# TYPE THIS: check. The signature and docstring are given; you type the body.
# Its finished copy is techcorp/agent/permissions.py.
def check(tool_name: str, args: dict, ctx) -> dict | None:
    """None when the caller in the envelope may make this call; otherwise a typed miss naming the role, the tool and why."""
    caller = (getattr(ctx, "user_id", None) or "").strip()
    role = getattr(ctx, "role", None) or "employee"
    region = getattr(ctx, "region", None) or "US"

    def miss(reason: str) -> dict:
        return {"found": False, "reason": reason, "role": role, "tool": tool_name}

    rule = RULES.get(tool_name)
    if rule is None:
        return miss(f"no rule allows {tool_name}")
    if not caller:
        return miss("no acting user in the request envelope")
    if _find_user(caller) is None:
        return miss(f"unknown caller {caller}")
    if role not in rule["roles"]:
        return miss(f"role {role} may not call {tool_name}")
    target = caller if rule["target"] == "caller" else str(args.get(rule["target"]) or "")
    row = _find_user(target)
    if row is None:
        return None
    if role == "employee" and row["user_id"].lower() != caller.lower():
        return miss("an employee may act on their own account only")
    if row.get("region") != region:
        return miss(f"{row['user_id']} is in region {row.get('region')}; this desk serves {region}")
    if rule.get("listed_share"):
        share = str(args.get("share") or "")
        if share not in SHARES:
            return miss(f"share {share} is not on the share list")
        if row.get("department") not in SHARES[share]:
            return miss(f"share {share} is for {', '.join(SHARES[share])}")
    return None


# BREAK: delete the two lines that start with if row.get("region") and its return, and run. The US IT
# agent's grant for an EU employee now parks for a person, and python -m pytest tests/test_lab_05_30.py -q
# goes red. Put the two lines back and run.

GRANT_ARGS = {"user_id": "E-4104", "share": "finance-q3"}
for label, ctx, tool, args in (
    ("employee_grant", DeskContext(user_id="E-4104", role="employee", region="EU"), "grant_access", GRANT_ARGS),
    ("eu_agent_grant", DeskContext(user_id="E-4106", role="it_agent", region="EU"), "grant_access", GRANT_ARGS),
    ("us_agent_grant", DeskContext(user_id="E-4101", role="it_agent", region="US"), "grant_access", GRANT_ARGS),
    ("empty_reset", DeskContext(), "reset_password", {"user_id": "E-4102"}),
):
    print("check", label, json.dumps(check(tool, args, ctx)))

# %%
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
# write_gate first, PermissionGate after it: after_model hooks run last to first, so the rules answer
# before the gate could park. region_prompt writes the desk's region into the system prompt.
desk = build_techcorp_desk(model=chat, middleware=[write_gate(), PermissionGate(checker=check), region_prompt], checkpointer=InMemorySaver())
AGENT_TICKET = "Ticket TC-1004: Tomas Alvarez (E-4104) needs read access to the finance-q3 share for the Q3 close. Please grant it."
runs = (
    ("employee", "Ticket TC-1004 for employee E-4104: Please grant me read access to the finance-q3 share for Q3 close.", dict(user_id="E-4104", role="employee", region="EU")),
    ("eu_agent", AGENT_TICKET, dict(user_id="E-4106", role="it_agent", region="EU")),
    ("us_agent", AGENT_TICKET, dict(user_id="E-4101", role="it_agent", region="US")),
    ("empty_envelope", "Ticket TC-1097: I am E-4102. Please reset my password.", dict(user_id=None)),
)
for label, text, envelope in runs:
    state = run_ticket(desk, text, thread_id=f"lab-4-30-{label}", **envelope)
    parked = state["__interrupt__"][0].value["action_requests"] if state.get("__interrupt__") else []
    print(label, "parked", [(r["name"], r["args"]) for r in parked])
    for message in state["messages"]:
        if message.type == "tool":
            print(label, "tool", message.name, message.status, message.content)
    if not parked:
        print(label, "reply", reply_text(state).strip())
# A parked grant waits for a person and an approver (lecture 4.28); this lab leaves it parked.
