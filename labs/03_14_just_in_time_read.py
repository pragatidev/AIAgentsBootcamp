# %% [markdown]
# Add a just-in-time file read.
#
# The read tool fires only on the ticket that needs it. Print which
# tickets triggered a read and the token totals vs preloading.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import (
    ContextAgent,
    context_caller,
    count_tokens,
    read_file,
)
from dataflow.context.map_text import MAP, get_fat

RETURN_TICKET = "What is your return window for a delivered desk lamp?"
SHIP_TICKET = "How many business days is standard shipping inside the country?"

# %%
jit = ContextAgent(
    context_caller(enable_read=True, enable_notes=False),
    system=MAP,
    cap=6,
)
ret = jit.run(RETURN_TICKET)
print("return_ticket_tools", ret["tool_names"])
print("return_ticket_reads", ret["reads"])
print("return_ticket_final", ret["final"])
print("return_ticket_tokens", count_tokens(ret["messages"]))

ship_agent = ContextAgent(
    context_caller(enable_read=True, enable_notes=False),
    system=MAP,
    cap=6,
)
ship = ship_agent.run(SHIP_TICKET)
print("ship_ticket_tools", ship["tool_names"])
print("ship_ticket_reads", ship["reads"])
print("ship_ticket_final", ship["final"])
print("ship_ticket_tokens", count_tokens(ship["messages"]))

# %%
pre = ContextAgent(
    context_caller(enable_read=False, enable_notes=False),
    system=MAP,
    preload=get_fat(),
    cap=1,
)
pre_out = pre.run(RETURN_TICKET)
print("preload_tokens", count_tokens(pre_out["messages"]))
print("preload_final", pre_out["final"])
print("jit_return_tokens", count_tokens(ret["messages"]))
print(
    "read_only_on_match",
    "return_policy.md" in " ".join(ret["reads"])
    or any("return" in str(x).lower() for x in ret["reads"]),
)
