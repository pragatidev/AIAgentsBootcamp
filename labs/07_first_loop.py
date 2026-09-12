# %%
"""S7.2 First agent loop. Fixture until a key exists. create_agent is the live path, not this file's default.
The retired agent factory from 2025 does not ship.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.agent.loop import AgentLoop
from dataflow.tools.escalate import escalate_to_human
from dataflow.tools.orders import lookup_order_from_ticket
from dataflow.tools.policy import read_policy

# %%
loop = AgentLoop(
    tools={
        "orders": lookup_order_from_ticket,
        "policy": read_policy,
        "escalate": escalate_to_human,
    }
)

# %%
out = loop.run("Can I return order DF-1001?")
print("ticket", out["ticket"])
for step in out["steps"]:
    print("action", step["action"])
