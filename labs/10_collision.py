# %%
"""S10.5 Plant a collision, then apply the reducer."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.errors import InvalidUpdateError

from dataflow.graphs.collision import build_collision, build_reduced

# %%
try:
    build_collision().invoke({"ticket": "DF-1001", "log": ""})
    print("collision", "unexpected_success")
except InvalidUpdateError as exc:
    print("collision", type(exc).__name__)
    print("detail", str(exc).split("\n")[0])

# %%
out = build_reduced().invoke({"ticket": "DF-1001", "log": []})
print("reduced_log", out.get("log"))
