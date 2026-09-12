# %% [markdown]
# Command versus a conditional edge.
#
# When this works, the same ticket takes the same route through
# build_v2_route and build_v2_command, and both mermaid drawings
# print so you can see the two ways side by side.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.v2_command import build_v2_command
from dataflow.graphs.v2_route import build_v2_route

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
ticket = None
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    if row["ticket_id"] == "T-3002":
        ticket = row
        break
print("ticket_id", ticket["ticket_id"])
print("text", ticket["text"])
print("model", config.CHAT_MODEL)

# %%
edge_graph = build_v2_route()
command_graph = build_v2_command()
payload = {"ticket": ticket["text"]}
edge_state = edge_graph.invoke(payload)
command_state = command_graph.invoke(payload)
print("edge_route", edge_state.get("route"))
print("edge_reply", edge_state.get("reply"))
print("command_route", command_state.get("route"))
print("command_reply", command_state.get("reply"))

# %%
print("edge_mermaid")
print(edge_graph.get_graph().draw_mermaid())
print("command_mermaid")
print(command_graph.get_graph().draw_mermaid())
