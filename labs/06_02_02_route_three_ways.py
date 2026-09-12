# %% [markdown]
# Route billing, policy and escalate with a real model.
#
# When this works, three tickets from tickets.jsonl take three
# routes, each prints ticket_id, route, and reply, and the mermaid
# drawing labels the conditional edges.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.v2_route import build_v2_route

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

# T-3002 names an order, T-3003 asks a policy, T-3027 asks to escalate.
chosen_ids = ["T-3002", "T-3003", "T-3027"]
print("chosen_ticket_ids", chosen_ids)
print("model", config.CHAT_MODEL)
for ticket_id in chosen_ids:
    print("chosen", ticket_id, by_id[ticket_id]["text"])

# %%
graph = build_v2_route()
for ticket_id in chosen_ids:
    ticket = by_id[ticket_id]
    state = graph.invoke({"ticket": ticket["text"]})
    print("ticket_id", ticket_id)
    print("route", state.get("route"))
    print("reply", state.get("reply"))
    print("---")

# %%
print("mermaid")
print(graph.get_graph().draw_mermaid())
