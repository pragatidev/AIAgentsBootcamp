# %%
"""S2.4 Read an agent loop in Python. No framework yet."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.agent.loop import run_loop
from dataflow.tools.escalate import escalate_to_human
from dataflow.tools.orders import lookup_order_from_ticket
from dataflow.tools.policy import read_policy

# %%
tools = {
    "orders": lookup_order_from_ticket,
    "policy": read_policy,
    "escalate": escalate_to_human,
}

# %%
ticket = "Can I return order DF-1001?"
out = run_loop(ticket, tools)
print("ticket", out["ticket"])
for step in out["steps"]:
    print("action", step["action"])
    print("result", step["result"])
