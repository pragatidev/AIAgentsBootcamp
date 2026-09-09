# %%
"""S2.4 Read an agent loop in Python. No framework yet."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from northstar.agent.loop import run_loop
from northstar.tools.escalate import escalate_to_human
from northstar.tools.orders import lookup_order
from northstar.tools.policy import read_policy

# %%
tools = {
    "orders": lookup_order,
    "policy": read_policy,
    "escalate": escalate_to_human,
}

# %%
ticket = "Can I return order NS-1001?"
out = run_loop(ticket, tools)
print("ticket", out["ticket"])
for step in out["steps"]:
    print("action", step["action"])
    print("result", step["result"])
