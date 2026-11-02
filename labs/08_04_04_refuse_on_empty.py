# %%
"""Lab 25.4: make DataFlow refuse on empty retrieve.

What we build: you type the small check that tells the DataFlow graph to refuse: nothing survived the grade
and the one rewrite is spent. You check it on five states, hand it to the graph, and ask the customer desk
about coffee beans, printing what each pass retrieved and what the grader kept. Then you break the check the
obvious way, by testing whether the search came back empty.

What you learn: 25.3's idea made real. Refusing is an edge that reads the state and replies with one fixed
sentence, not a prompt; and empty means empty after the grade, because a vector search always returns
something. A check that reads the retrieve instead answers from passages the grader rejected, and cites them.

What will be true on your screen: five should_refuse rows, then for each pass retrieved N kept M with the
grades, the rewritten question between the passes, the edge taken, the refusal and REFUSE True. Then
python -m pytest tests/test_lab_08_04_04.py -q passes.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.crag import MAX_REWRITES
from dataflow.graphs.rag_graph import build_rag_graph


# %%
# TYPE THIS: should_refuse. The signature and docstring are given; you type the body.
# Its finished copy is should_refuse in dataflow/graphs/crag.py.
def should_refuse(state: dict, *, max_rewrites: int = MAX_REWRITES) -> bool:
    """True when the grader kept nothing (no keep label and no graded passage) and the rewrite budget is spent. Retrieval may still have returned passages: empty means nothing survived the grade."""
    kept = [row for row in state.get("grades") or [] if row.get("label") == "keep"]
    if kept or state.get("graded"):
        return False
    return int(state.get("rewrites") or 0) >= int(max_rewrites)


# BREAK: test the retrieve instead of the grade. Replace the body with
#     return not state.get("passages") and int(state.get("rewrites") or 0) >= int(max_rewrites)
# run the lab, then python -m pytest tests/test_lab_08_04_04.py -q and read the red line.
# git checkout -- labs/08_04_04_refuse_on_empty.py puts it back.

THREE_DROPS = {"passages": [{"source": "a"}, {"source": "b"}, {"source": "c"}], "grades": [{"label": "drop"}] * 3}
ROWS = [
    {"grades": [{"label": "keep"}], "rewrites": 0},
    {**THREE_DROPS, "rewrites": 0},
    {**THREE_DROPS, "rewrites": 1},
    {"passages": [], "grades": [], "rewrites": 1},
    {"grades": [], "graded": [{"source": "dataflow/wiki/return_policy.md"}], "rewrites": 1},
]
for state in ROWS:
    shown = {key: (len(value) if isinstance(value, list) else value) for key, value in state.items()}
    print("should_refuse", shown, "->", should_refuse(state))


# %%
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
graph = build_rag_graph(model=chat, refuse_check=should_refuse)
question = "Do you sell coffee beans in the DataFlow shop?"
print("desk customer")
print("question", question)
state: dict = {}
retrieved = 0
for update in graph.stream({"question": question}, {"recursion_limit": 12}, stream_mode="updates"):
    for node, payload in update.items():
        payload = payload or {}
        state.update(payload)
        if node == "retrieve":
            retrieved = len(payload.get("passages") or [])
        elif node == "grade":
            print("retrieved", retrieved, "kept", len(payload.get("graded") or []))
            for row in payload.get("grades") or []:
                print("  GRADE", row["label"], row["source"])
        elif node == "rewrite":
            print("rewritten", repr(payload.get("rewritten_question")))
        elif node in ("generate", "refuse"):
            print("edge_taken", node)


# %%
reply = str(state.get("reply") or "")
print(reply)
rejected = {row["source"] for row in state.get("grades") or [] if row["label"] != "keep"}
cited = {row.get("source") for row in state.get("sources") or []}
print("REFUSE", reply.startswith("I do not have that in the knowledge base"))
print("cites_rejected", bool(cited & rejected))
