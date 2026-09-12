# %% [markdown]
# Make DataFlow refuse on empty retrieve.
#
# When this works, a question the knowledge base does not cover prints
# REFUSE and no invented policy. Force generate on empty and a fluent
# fabricated policy appears. Restore refuse.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from config import CHAT_MODEL
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.tools.retrieve import get_index

print("model", CHAT_MODEL)
print("building_index")
get_index()
print("index_ready")

uncovered = "Do you sell coffee beans in the DataFlow shop?"
print("uncovered", uncovered)
graph = build_rag_graph(scope="all")
state = graph.invoke({"question": uncovered})
print("route", state.get("route"))
print("rewrites", state.get("rewrites"))
print("reply")
print(state.get("reply"))
print(
    "REFUSE",
    "I do not have that in the knowledge base" in str(state.get("reply") or ""),
)

# %%
print("break_force_generate_on_empty")
forced = build_rag_graph(scope="all", force_generate_on_empty=True, max_rewrites=0)
fabricated = forced.invoke({"question": uncovered})
print("FABRICATED")
print(fabricated.get("answer") or fabricated.get("reply"))
print("forced_refused", "I do not have that in the knowledge base" in str(fabricated.get("reply") or ""))

# %%
print("restore_refuse")
restored = build_rag_graph(scope="all", force_generate_on_empty=False)
again = restored.invoke({"question": uncovered})
print("restore_reply")
print(again.get("reply"))
