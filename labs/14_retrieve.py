# %%
"""S14.3 Retrieve the wiki. Empty hit refuses. Keyword stand-in, not FAISS."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The keyword stand-in lives in dataflow.tools.policy. dataflow.tools.retrieve is the FAISS tool,
# which always returns its nearest passages, so it never shows an empty hit.
from dataflow.tools.policy import search_policy

# %%
hit = search_policy.invoke({"question": "Can I return an unused item after delivery?"})
print("hit_found", hit["found"])
print("hit_path", hit.get("path"))

# %%
miss = search_policy.invoke({"question": "What is the weather on Mars?"})
print("miss_found", miss["found"])
print("miss_refuse", not miss["found"], miss.get("reason"))
