# %%
"""Lab 4.12: build the TechCorp IT desk with create_agent.

What we build: you turn the three TechCorp tools and the five-band prompt into a working IT desk with
one call you type yourself, run three real tickets through it, read every hop, then take the reset tool
away and put it back.

What you learn: create_agent is the loop you wrote in Section 3, in one call, handed back as a compiled
graph with a model node, a tools node and the cycle between them. The tool list is the desk's abilities:
a missing tool is a missing ability, not a missing word in the prompt.

What will be true on your screen: the graph's nodes; for each ticket every message with its type, the
tool calls the model asked for, and on each AI message why the model stopped (done_reason) and its
tokens; then whether the reply is in the desk's refusal shape. This desk has no gate yet, so a reset
runs at once; lecture 4.14 puts a person in front of it.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents import create_agent

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import reply_text, run_ticket
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT
from techcorp.tools.accounts import grant_access, lookup_user, reset_password

# %%
# TYPE THIS: the tool list and build_desk. The signature and docstring are given; you type the rest.
# The package's own builder is build_techcorp_desk in techcorp/agent/desk.py.
TOOLS = [lookup_user, reset_password, grant_access]


def build_desk(model, tools, system_prompt):
    """create_agent with the TechCorp envelope; returns the compiled graph."""
    return create_agent(model=model, tools=list(tools), system_prompt=system_prompt, context_schema=DeskContext)


# BREAK: delete reset_password from TOOLS and run. TC-1001 gets no password, because the desk cannot
# do it any more; read its done_reason and reply. Put reset_password back and run.

# reasoning=False: with thinking on, the password ticket thought until the 4096-token cap and never answered.
chat = config.get_chat_model(reasoning=False)
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
desk = build_desk(chat, TOOLS, DESK_SYSTEM_PROMPT)
print("desk_type", type(desk).__name__)
print("nodes", list(desk.get_graph().nodes))


# %%
def print_transcript(state: dict) -> None:
    for n, message in enumerate(state["messages"]):
        line = [str(n), message.type]
        if message.type == "tool":
            line += [message.name, str(message.content)]
        elif message.type == "ai":
            line += ["calls", json.dumps([(c["name"], c["args"]) for c in message.tool_calls])]
            line += ["done_reason", str(message.response_metadata.get("done_reason"))]
            line += ["tokens", str((message.usage_metadata or {}).get("total_tokens"))]
            line += ["text", message.text.strip()]
        else:
            line += [message.text.strip()]
        print(" ".join(line))


tickets = (root / "techcorp" / "data" / "tickets.jsonl").read_text(encoding="utf-8").splitlines()
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets)}
for ticket_id in ("TC-1001", "TC-1002", "TC-1003"):
    ticket = by_id[ticket_id]
    text = f"Ticket {ticket_id} for employee {ticket['customer_id']}: {ticket['text']}"
    state = run_ticket(desk, text, user_id=ticket["customer_id"])
    print("ticket", ticket_id, "message_count", len(state["messages"]))
    print_transcript(state)
    reply = reply_text(state).strip()
    if not reply:
        print("EMPTY_REPLY")
    print("refusal_shape", reply.startswith("I cannot help with that from the IT desk:"))
