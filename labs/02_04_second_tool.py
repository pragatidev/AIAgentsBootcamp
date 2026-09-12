# %% [markdown]
# Give it a second tool and watch it choose.
#
# lookup_user plus reset_password. TC-1001 should lookup then reset.
# A VPN question should only lookup. Print the choices.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from techcorp.agent.scratch import (
    ScratchAgent,
    lookup_user,
    openai_caller,
    reset_password,
    tool_schema,
)

tools_schema = [
    tool_schema(
        "lookup_user",
        "Look up a TechCorp employee by user_id. Use this for account, VPN, or status questions.",
    ),
    tool_schema(
        "reset_password",
        "Reset a TechCorp employee laptop password. Use only when they ask to reset a password.",
    ),
]
tools = {"lookup_user": lookup_user, "reset_password": reset_password}
caller = openai_caller(tools_schema)

PASSWORD = (
    "TC-1001 user E-4101: I forgot my laptop password after the long "
    "weekend. Please reset it."
)
VPN = (
    "TC-1002 user E-4102: VPN connects then drops every few minutes "
    "from the home office. What is on this account?"
)


def print_run(label: str, ticket: str) -> None:
    agent = ScratchAgent(caller, tools, cap=8)
    out = agent.run(ticket)
    names = [row["name"] for row in out["rounds"] if row["kind"] == "tool"]
    print("ticket", label)
    print("choices", names)
    for row in out["rounds"]:
        if row["kind"] == "tool":
            print("round", row["round"], "tool", row["name"], json.dumps(row["arguments"]))
        elif row["kind"] == "final":
            print("round", row["round"], "final", row["content"])
    print("stop", out["stop"])
    print("final_answer", out["final"])


# %%
print_run("password_TC-1001", PASSWORD)

# %%
print_run("vpn_TC-1002", VPN)
