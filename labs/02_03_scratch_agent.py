# %% [markdown]
# Build an agent from scratch.
#
# One tool, a model that can ask for it, and a loop that runs the tool and
# hands the result back. The loop stops when the model answers without
# asking for a tool, or after CAP rounds. Ticket TC-1001. Print every round.
# The model is always your local Ollama model; a cloud key changes nothing.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from techcorp.agent.scratch import SYSTEM, openai_caller, reset_password, tool_schema

CAP = 8
TICKET = (
    "TC-1001 user E-4101: I forgot my laptop password after the long "
    "weekend. Please reset it."
)
tools_schema = [
    tool_schema(
        "reset_password",
        "Reset a TechCorp employee laptop password. Requires user_id.",
    )
]
TOOLS = {"reset_password": reset_password}
call_model = openai_caller(tools_schema)
print("cap", CAP)
print("ticket", TICKET)


# %%
def run_agent(ticket: str, cap: int = CAP) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": ticket},
    ]
    for n in range(1, cap + 1):
        reply = call_model(messages)
        if not reply["tool_calls"]:
            print("round", n, "final", reply["content"])
            return "final"
        messages.append(
            {
                "role": "assistant",
                "content": reply["content"],
                "tool_calls": reply["raw_tool_calls"],
            }
        )
        for tc in reply["tool_calls"]:
            result = TOOLS[tc["name"]](**tc["arguments"])
            print("round", n, "tool", tc["name"], json.dumps(tc["arguments"]))
            print("result", result)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    print("final", "desk could not finish")
    return "cap"


print("stop", run_agent(TICKET))
