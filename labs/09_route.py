# %%
"""S9.2 Route billing vs policy vs escalate. No model."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from northstar.graphs.v2_route import build_v2_route

# %%
graph = build_v2_route()
tickets = [
    "Can I return order NS-1001?",
    "What is your shipping time?",
    "I want a human manager please",
]
for ticket in tickets:
    out = graph.invoke({"ticket": ticket})
    print("ticket", ticket)
    print("route", out.get("route"))
    print("found", (out.get("result") or {}).get("found"))
    print("escalate", (out.get("result") or {}).get("escalate"))
    print("---")
