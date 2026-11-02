# %%
"""Lab 25.4: make DataFlow refuse on empty retrieve.

What we build: you type the small check that tells the DataFlow graph to refuse: nothing survived the grade
and the one rewrite is spent. You check it on five states, hand it to the graph, and ask the customer desk
about coffee beans, printing what each pass retrieved and what the grader kept. Then you break it two ways:
test whether the search came back empty, and switch the refuse check off to read what the model writes.

What you learn: 25.3's idea made real. Refusing is an edge that reads the state and replies with one fixed
sentence, not a prompt; and empty means empty after the grade, because a vector search always returns
something. A check on the retrieve answers from rejected passages; with no check, a prompt is the only guard.

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
from dataflow.graphs.rag_graph import build_rag_graph, grade


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

# BREAK 2, the refuse check switched off: set REFUSE_CHECK_ON = False and run the lab. The graph still grades and
# rewrites once, then generates where it would have refused, on what the grade kept (nothing, for this question),
# with the normal generate prompt: answer only from the passages, say you do not have it, do not invent a policy.
# No line tells the model to invent. Read the reply your model writes; it can differ from run to run. Then
# python -m pytest tests/test_lab_08_04_04.py -q, and set it back to True (or git checkout) for the refusal.
REFUSE_CHECK_ON = True

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
if REFUSE_CHECK_ON:
    graph = build_rag_graph(model=chat, refuse_check=should_refuse)
else:
    # When the grade kept nothing, generate falls back to every retrieved passage (BREAK 1 shows that). This
    # grade hands generate only what it kept, so with the check off generate reads exactly the kept set.
    def grade_kept_only(state, runtime=None, *, model=None):
        out = grade(state, runtime=runtime, model=model)
        return {**out, "passages": out["graded"]}

    graph = build_rag_graph(model=chat, refuse_check=lambda state, **_: False, grade_fn=grade_kept_only)
print("refuse_check", "on" if REFUSE_CHECK_ON else "off")
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
            if node == "generate":
                print("generate_read", len(state.get("graded") or state.get("passages") or []), "passages")


# %%
reply = str(state.get("reply") or "")
print(reply)
rejected = {row["source"] for row in state.get("grades") or [] if row["label"] != "keep"}
cited = {row.get("source") for row in state.get("sources") or []}
print("REFUSE", reply.startswith("I do not have that in the knowledge base"))
print("cites_rejected", bool(cited & rejected))
