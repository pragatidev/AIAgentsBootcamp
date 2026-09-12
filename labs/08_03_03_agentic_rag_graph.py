# %% [markdown]
# Build the DataFlow agentic RAG graph.
#
# When this works, a paraphrase of the refund policy prints the route,
# retrieved sources with scores, every grade with its reason, the
# answer and the sources. Skip grade and a wrong chunk can be cited;
# add grade and the chunk drops.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from config import CHAT_MODEL
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.rag.faiss_index import search
from dataflow.tools.retrieve import get_index

print("model", CHAT_MODEL)
print("building_index")
index = get_index()
print("index_ready", type(index).__name__)

question = "Can I send back an unused lamp after twelve days?"
print("question", question)
graph = build_rag_graph()
state = graph.invoke({"question": question})
print("route", state.get("route"))
print("rewrites", state.get("rewrites"))
print("rewritten_question", state.get("rewritten_question"))
print("retrieved")
for row in state.get("passages") or []:
    print("source", row.get("source"), "folder", row.get("folder"), "score", row.get("score"))
    print("text", str(row.get("text") or "")[:240])
print("grades")
for row in state.get("grades") or []:
    print("GRADE", row.get("label"), "source", row.get("source"))
    print("reason", row.get("reason"))
print("answer")
print(state.get("answer"))
print("sources", state.get("sources"))
print("reply")
print(state.get("reply"))

# %%
print("break_grade_disabled")
candidates = [
    "Can I send back an unused lamp after twelve days?",
    "What is the return policy for equipment?",
    "Do I have to return company equipment after I leave?",
]
chosen = None
for text in candidates:
    hits = search(index, text, k=3, folder=None)
    sources = [str(hit.get("source") or "") for hit in hits]
    has_handbook = any("employee_handbook" in src.replace("\\", "/") for src in sources)
    print("probe", text)
    print("probe_sources", sources)
    print("handbook_in_top_k", has_handbook)
    if has_handbook and chosen is None:
        chosen = text
if chosen is None:
    chosen = candidates[-1]
    print("handbook_not_in_top_k_using", chosen)
else:
    print("handbook_question", chosen)

broken = build_rag_graph(grade_enabled=False, scope="all")
wrong = broken.invoke({"question": chosen})
print("no_grade_route", wrong.get("route"))
print("no_grade_sources", wrong.get("sources"))
print("no_grade_answer")
print(wrong.get("answer"))
cited = " ".join(
    str(row.get("source") or "") for row in (wrong.get("sources") or [])
)
print("cited_handbook", "employee_handbook" in cited.replace("\\", "/"))

# %%
print("restore_grade_enabled")
restored = build_rag_graph(grade_enabled=True)
again = restored.invoke({"question": question})
print("restore_route", again.get("route"))
print("restore_grades")
for row in again.get("grades") or []:
    print("GRADE", row.get("label"), row.get("source"), row.get("reason"))
print("restore_sources", again.get("sources"))
