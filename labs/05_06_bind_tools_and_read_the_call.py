# %%
"""Lab 4.6: bind_tools and read the tool call the model proposed.

What we build: we hand the desk's three tools to the real model from config.py, send it ticket
TC-1001, and read what it asks for: a tool name, the arguments and an id. Then you are the loop. You
type answer_calls, which runs each call and sends each result back with its own id, and we go round
until the model writes a sentence. Then we break the id on purpose and watch a check catch it.

What you learn: the model never runs a tool. It writes a request, and your code decides whether and
how to run it. The tool call id is the thread that pairs each result with its request, which matters
most when one turn asks for two things.

What will be true on your screen: max_hops 3, each hop's proposed calls with their ids, each result
with the id it answers, an about_to_run line before any write, pairing [] after the loop, the stop
reason, and the model's final sentence. Which tool it asks for first is the model's choice.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

import config
from techcorp.agent.by_hand import check_pairing
from techcorp.tools.accounts import dummy_runtime, grant_access, lookup_user, reset_password

tickets = (root / "techcorp" / "data" / "tickets.jsonl").read_text(encoding="utf-8").splitlines()
ticket = next(row for row in map(json.loads, tickets) if row["ticket_id"] == "TC-1001")

TOOLS = {t.name: t for t in (lookup_user, reset_password, grant_access)}
model = config.get_chat_model()
bound = model.bind_tools(list(TOOLS.values()))
print("model", type(model).__name__, getattr(model, "model", None) or getattr(model, "model_name", None))
print("ticket_id", ticket["ticket_id"])

# The request envelope: the ticket's owner, never the id the model types (lecture 4.19 explains it).
runtime = dummy_runtime(ticket["customer_id"])


# %%
# TYPE THIS: answer_calls. The signature and docstring are given; you type the body.
# Its finished copy is techcorp/agent/by_hand.py.
def answer_calls(ai, runtime) -> list:
    """One ToolMessage for every call the model proposed, each carrying that call's own id."""
    answers = []
    for call in ai.tool_calls:
        name, args = call["name"], call["args"]
        if name == "reset_password":
            result = reset_password.func(str(args.get("user_id") or ""), runtime=runtime)
        elif name in TOOLS:
            try:
                result = TOOLS[name].invoke(args)
            except ValidationError:
                result = {"found": False, "reason": f"bad arguments for {name}"}
        else:
            result = {"found": False, "reason": f"unknown tool {name}"}
        answers.append(ToolMessage(content=json.dumps(result), tool_call_id=call["id"], name=name))
    return answers


# BREAK: change tool_call_id=call["id"] to tool_call_id="not-the-real-id" and run. The pairing line
# names every unanswered call and every stray result; read what the model says. Put call["id"] back.

# %%
MAX_HOPS = 3
print("max_hops", MAX_HOPS)
history = [
    SystemMessage(content="Use tools. Look up the user before you reset. Never reset without a user id."),
    HumanMessage(content=f"Ticket {ticket['ticket_id']} for employee {ticket['customer_id']}: {ticket['text']}"),
]
stop = "max_hops"
for hop in range(1, MAX_HOPS + 1):
    ai = bound.invoke(history)
    if not ai.tool_calls:
        print("hop", hop, "final", ai.text.strip())
        stop = "final"
        break
    for call in ai.tool_calls:
        print("hop", hop, "proposed", call["name"], json.dumps(call["args"]), "id", call["id"])
        if call["name"] in ("reset_password", "grant_access"):
            # You are the loop, so you are the gate. Lecture 4.14 puts a person here.
            print("about_to_run", call["name"], "for", runtime.context.user_id)
    answers = answer_calls(ai, runtime)
    for answer in answers:
        print("hop", hop, "result for", answer.tool_call_id, answer.content)
    history += [ai, *answers]

print("pairing", check_pairing(history))
print("stop", stop)
