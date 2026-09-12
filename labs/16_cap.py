# %%
"""S16.2 Plant a cycle. Recursion limit stops it. Log the reason."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.graphs.runaway import run_with_cap

# %%
out = run_with_cap(8)
print("stopped", out["stopped"])
print("reason", out["reason"])
print("detail", out.get("detail"))
