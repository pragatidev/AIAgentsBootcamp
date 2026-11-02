# %%
"""Lab 24.5: add corrective RAG to the DataFlow graph.

What we build: you type the one function that decides what the DataFlow graph does after it grades a
search: answer, search again in better words, or say it does not know. You check it on six states before any
model runs, then give it to the graph and watch both grade passes on a badly phrased question, and the
refusal on a question the knowledge base does not cover. Then you break it so the loop has no exit.

What you learn: 24.4's idea made real. When the graded set is bad, correct the search, not the answer;
rewrite once, refuse after that, and the cap is what makes the refuse edge reachable. The run carries a
recursion limit of 12 because LangGraph's own default here is 10007 steps.

What will be true on your screen: six after_grade rows (generate, rewrite, refuse, widen, generate,
refuse), then for the badly phrased question each grade pass, the rewritten question with rewrites 1, the
second pass and corrected True or False, then the refusal for the uncovered question and REFUSE True. Then
python -m pytest tests/test_lab_08_03_05.py -q passes.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.errors import GraphRecursionError

import config
from dataflow.graphs.crag import MAX_REWRITES
from dataflow.graphs.rag_graph import build_rag_graph


# %%
# TYPE THIS: after_grade. The signature and docstring are given; you type the body.
# Its finished copy is after_grade in dataflow/graphs/crag.py, the edge every later graph uses.
def after_grade(state: dict, *, max_rewrites: int = MAX_REWRITES, web_search_allowed: bool = False) -> str:
    """Pick the edge after the grade node: generate when at least one passage was kept, rewrite when none was kept and a rewrite is left, widen when none is left and the company allows widening, otherwise refuse."""
    kept = [row for row in state.get("grades") or [] if row.get("label") == "keep"] or list(state.get("graded") or [])
    if kept:
        return "generate"
    if int(state.get("rewrites") or 0) < int(max_rewrites):
        return "rewrite"
    if web_search_allowed:
        return "widen"
    return "refuse"


# BREAK: let the loop run forever. Change
#     if int(state.get("rewrites") or 0) < int(max_rewrites):
# to
#     if True:
# run the lab, then python -m pytest tests/test_lab_08_03_05.py -q and read the red line.
# git checkout -- labs/08_03_05_corrective_rag.py puts it back.

ROWS = [
    ({"grades": [{"label": "keep"}], "rewrites": 0}, False),
    ({"grades": [{"label": "wrong"}], "rewrites": 0}, False),
    ({"grades": [{"label": "wrong"}], "rewrites": 1}, False),
    ({"grades": [{"label": "wrong"}], "rewrites": 1}, True),
    ({"grades": [], "graded": [{"source": "dataflow/wiki/return_policy.md"}]}, False),
    ({"grades": [{"label": "drop"}], "rewrites": 2}, False),
]
for state, allowed in ROWS:
    print("after_grade", state, "web_search_allowed", allowed, "->", after_grade(state, web_search_allowed=allowed))


# %%
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
graph = build_rag_graph(model=chat, policy=after_grade)


def stream(question: str) -> dict:
    """Print each node's update as it lands; return the final state. A loop with no exit stops at the limit of 12."""
    print("question", question)
    final: dict = {}
    try:
        for update in graph.stream({"question": question}, {"recursion_limit": 12}, stream_mode="updates"):
            for node, payload in update.items():
                payload = payload or {}
                final.update(payload)
                if node == "grade":
                    print("grade_pass", "kept", len(payload.get("graded") or []), "of", len(payload.get("grades") or []))
                    for row in payload.get("grades") or []:
                        print("  GRADE", row["label"], row["source"], "|", row["reason"])
                elif node == "rewrite":
                    print("rewrite", repr(payload.get("rewritten_question")), "rewrites", payload.get("rewrites"))
                elif node in ("generate", "refuse", "lookup", "answer"):
                    print("edge_taken", node)
    except GraphRecursionError as err:
        print("runaway", type(err).__name__, str(err).splitlines()[0])
    return final


# %%
# A badly phrased question: does the rewrite find a passage the first search missed?
state = stream("how do I file a TPS report for an unused desk lamp return")
print("rewrites", state.get("rewrites") or 0)
print("corrected", bool(state.get("rewrites")) and bool(state.get("graded")))
print("reply", state.get("reply"))


# %%
# A question the knowledge base does not cover.
state = stream("Do you offer a student discount on the Enterprise plan?")
print("reply", state.get("reply"))
print("REFUSE", str(state.get("reply") or "").startswith("I do not have that in the knowledge base"))
