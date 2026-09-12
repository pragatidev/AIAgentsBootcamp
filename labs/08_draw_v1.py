# %%
"""S8.3 Draw the three-node line. No model. Compile is required."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.graphs.v1_triage import build_v1_triage

# %%
g = build_v1_triage()
print("nodes", sorted(g.get_graph().nodes))
print("mermaid")
print(g.get_graph().draw_mermaid())
