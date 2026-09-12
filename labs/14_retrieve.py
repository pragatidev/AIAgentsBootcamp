# %%
"""S14.3 Retrieve the wiki. Empty hit refuses. Keyword stand-in, not FAISS."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.tools.retrieve import retrieve

# %%
hit = retrieve("Can I return an unused item after delivery?")
print("hit_found", hit["found"])
print("hit_path", (hit.get("hits") or [{}])[0].get("path"))

# %%
miss = retrieve("What is the weather on Mars?")
print("miss_found", miss["found"])
print("miss_refuse", miss.get("refuse"))
