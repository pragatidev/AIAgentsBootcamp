# %% [markdown]
# Print citations on a DataFlow answer.
#
# When this works, the refund authorization question prints an answer
# that ends with customer_support_procedures.markdown and its section.
# Strip sources in generate and the citation becomes Sources: none.
# Put them back and the file name returns.

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

question = "Who can approve a refund under 30 days?"
print("question", question)
graph = build_rag_graph(scope="all")
state = graph.invoke({"question": question})
print("route", state.get("route"))
print("reply")
print(state.get("reply"))
reply = str(state.get("reply") or "")
print(
    "names_procedures",
    "customer_support_procedures.markdown" in reply.replace("\\", "/"),
)

# %%
print("break_strip_sources")
stripped = build_rag_graph(scope="all", strip_sources=True)
broken = stripped.invoke({"question": question})
print("stripped_reply")
print(broken.get("reply"))
print("sources_none", "Sources: none" in str(broken.get("reply") or ""))

# %%
print("restore_sources")
restored = build_rag_graph(scope="all", strip_sources=False)
again = restored.invoke({"question": question})
print("restore_reply")
print(again.get("reply"))
