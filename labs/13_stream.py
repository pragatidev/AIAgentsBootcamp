# %%
"""S13.4 Stream node updates. No model tokens in the no-key path."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.graphs.v1_triage import build_v1_triage

# %%
graph = build_v1_triage()
print("stream_mode", "updates")
for event in graph.stream(
    {"ticket": "Can I return order DF-1001?"},
    stream_mode="updates",
):
    node = next(iter(event))
    print("node", node)
    print("keys", sorted((event[node] or {}).keys()))
