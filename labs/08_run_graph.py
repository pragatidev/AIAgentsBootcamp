# %%
"""S8.4 Invoke the three-node graph. No model."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.graphs.v1_triage import build_v1_triage

# %%
graph = build_v1_triage()
out = graph.invoke({"ticket": "Can I return order DF-1001?"})
print("route", out.get("route"))
print("found", (out.get("order") or {}).get("found"))
print("reply", out.get("reply"))
