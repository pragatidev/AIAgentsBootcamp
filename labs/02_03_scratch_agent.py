# %% [markdown]
# Build an agent from scratch.
#
# A while loop, tools on the raw endpoint, stop when the reply has no
# tool calls, cap of 8. Ticket TC-1001. Print every round.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from techcorp.agent.scratch import (
    ScratchAgent,
    openai_caller,
    reset_password,
    tool_schema,
)

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
print("cap", 8)
print("ticket", TICKET)

# %%
agent = ScratchAgent(
    openai_caller(tools_schema),
    {"reset_password": reset_password},
    cap=8,
)
out = agent.run(TICKET)
for row in out["rounds"]:
    if row["kind"] == "tool":
        print("round", row["round"], "tool", row["name"], json.dumps(row["arguments"]))
        print("result", row["result"])
    elif row["kind"] == "final":
        print("round", row["round"], "final", row["content"])
    else:
        print("round", row["round"], row)
print("stop", out["stop"])
print("final_answer", out["final"])
