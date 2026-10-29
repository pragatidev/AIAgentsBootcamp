# %% [markdown]
# Give it a second tool and watch it choose.
#
# Two tools on offer. Watch which one the model picks for each ticket.
# lookup_user reads a record, reset_password changes one. Then a break:
# the model is told about a tool the loop cannot run. Then the restore.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from techcorp.agent.scratch import (
    lookup_user,
    openai_caller,
    reset_password,
    run_loop,
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


def print_run(label: str, ticket: str, tools: dict) -> None:
    out = run_loop(caller, tools, ticket, cap=8)
    names = [row["name"] for row in out["rounds"] if row["kind"] == "tool"]
    print("ticket", label)
    print("choices", names)
    for row in out["rounds"]:
        if row["kind"] == "tool":
            print("round", row["round"], "tool", row["name"], json.dumps(row["arguments"]))
            print("result", row["result"])
        elif row["kind"] == "final":
            print("round", row["round"], "final", row["content"])
    print("stop", out["stop"])
    print("final_answer", out["final"])


# %%
print_run("password_TC-1001", PASSWORD, tools)

# %%
print_run("vpn_TC-1002", VPN, tools)

# %%
# Break: the model is still told about lookup_user, but the dict the loop
# runs no longer has it. Nothing crashes: the loop hands the model an
# "unknown tool" result instead.
drifted = {"reset_password": reset_password}
print_run("vpn_TC-1002_drifted", VPN, drifted)

# %%
# Restore: both names back in the dict, the same VPN ticket again.
print_run("vpn_TC-1002_restored", VPN, tools)
