# %%
"""S9.2 Route billing vs policy vs escalate. Fixture model, not a live call."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.graphs.v2_route import build_v2_route
from tests.fixtures.fake_model import FakeChatModel

# %%
tickets = [
    ("orders", "Can I return order DF-1001?"),
    ("policy", "What is your shipping time?"),
    ("escalate", "I want a human manager please"),
]
for route, ticket in tickets:
    graph = build_v2_route(model=FakeChatModel(route=route))
    out = graph.invoke({"ticket": ticket})
    print("ticket", ticket)
    print("route", out.get("route"))
    print("reply", out.get("reply"))
    print("---")
