# %% [markdown]
# Add corrective RAG to the DataFlow graph.
#
# When this works, a planted noise query prints GRADE=wrong, REWRITE,
# then the support procedures passage. A question the knowledge base
# does not cover prints REFUSE. Take the rewrite cap off and the
# recursion limit stops the loop with GraphRecursionError.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.errors import GraphRecursionError

from config import CHAT_MODEL
from dataflow.graphs.crag import MAX_REWRITES, build_crag
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.tools.retrieve import get_index

print("model", CHAT_MODEL)
print("MAX_REWRITES", MAX_REWRITES)
print("building_index")
get_index()
print("index_ready")

noise_candidates = [
    "lamp send-back window twelve spins, unused, not the shipping table",
    "how do I file a TPS report for an unused desk lamp return",
    "what is the P0 first response for an Enterprise customer",
]
graph = build_crag()

# %%
print("noise_search")
noise_used = None
noise_state = None
for text in noise_candidates:
    print("trying", text)
    state = graph.invoke({"question": text})
    grades = list(state.get("grades") or [])
    labels = [row.get("label") for row in grades]
    print("route", state.get("route"))
    print("rewrites", state.get("rewrites"))
    print("rewritten_question", state.get("rewritten_question"))
    print("grade_labels", labels)
    for row in grades:
        print("GRADE", row.get("label"), "source", row.get("source"))
        print("reason", row.get("reason"))
    if int(state.get("rewrites") or 0) >= 1:
        noise_used = text
        noise_state = state
        print("NOISE_QUERY", text)
        break
    print("---")
if noise_state is None:
    noise_used = noise_candidates[0]
    noise_state = graph.invoke({"question": noise_used})
    print("NOISE_QUERY_FALLBACK", noise_used)

print("after_rewrite_passages")
for row in noise_state.get("passages") or []:
    print("source", row.get("source"))
    print("text", str(row.get("text") or "")[:240])
print("answer")
print(noise_state.get("answer") or noise_state.get("reply"))

# %%
uncovered = "Do you offer a student discount on the Enterprise plan?"
print("uncovered", uncovered)
refuse_graph = build_rag_graph()
refused = refuse_graph.invoke({"question": uncovered})
print("uncovered_route", refused.get("route"))
print("uncovered_rewrites", refused.get("rewrites"))
print("uncovered_grades")
for row in refused.get("grades") or []:
    print("GRADE", row.get("label"), row.get("source"), row.get("reason"))
print("uncovered_reply")
print(refused.get("reply"))
print("REFUSE", "I do not have that in the knowledge base" in str(refused.get("reply") or ""))

# %%
print("break_uncapped_rewrites")
try:
    runaway = build_rag_graph(max_rewrites=50)
    runaway.invoke(
        {"question": uncovered},
        {"recursion_limit": 12},
    )
    print("runaway_unexpected_success")
except GraphRecursionError as err:
    print("GraphRecursionError", err)
except Exception as err:
    print("runaway_error", type(err).__name__ + ":", err)

# %%
print("restore_max_rewrites", MAX_REWRITES)
restored = build_rag_graph(max_rewrites=MAX_REWRITES)
again = restored.invoke({"question": uncovered})
print("restore_reply")
print(again.get("reply"))
