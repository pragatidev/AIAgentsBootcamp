# %%
"""Lab 24.3: build the DataFlow agentic RAG graph.

What we build: you type the grade node, plug it into the DataFlow agentic RAG graph, and print the graph's
nodes and edges so you see grade sitting between retrieve and generate. Then the lamp return question runs
twice: once on the customer pages, once on the whole knowledge base where the employee handbook can come
back. Then you break your grade so it keeps everything, and read what ends up cited.

What you learn: 24.1 and 24.2 made real. Route, retrieve, grade, generate and cite are nodes on one graph,
the model from config makes every decision, and grade reads each passage next to the question and drops
the near miss before generate can use it. Nearest is a distance, not an answer, and grading costs one model
call per passage.

What will be true on your screen: the model read off the object, the nodes and edges, then for each run the
route, the retrieved passages with their distances, every grade with its reason, the answer and its Sources,
whether the handbook was retrieved and whether it was cited, and the grade calls and seconds. Then
python -m pytest tests/test_lab_08_03_03.py -q passes.
"""

from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.rag_graph import GRADE_SYSTEM, Grade, build_rag_graph


# %%
# TYPE THIS: grade. The signature and docstring are given; you type the body.
# Its finished copy is grade in dataflow/graphs/rag_graph.py, which every later graph uses.
def grade(state: dict, runtime=None, *, model=None) -> dict:
    """Read each retrieved passage next to the question and label it keep, drop or wrong with a one sentence reason (the Grade schema). Return every grade under "grades" and only the kept passages under "graded"."""
    structured = model.with_structured_output(Grade)
    question = state.get("rewritten_question") or state.get("question") or ""
    grades, kept = [], []
    for passage in state.get("passages") or []:
        decision = structured.invoke(
            [
                {"role": "system", "content": GRADE_SYSTEM},
                {"role": "user", "content": f"Question: {question}\nSource: {passage.get('source')}\nPassage:\n{passage.get('text')}"},
            ]
        )
        label = str(decision.label)
        grades.append({"source": str(passage.get("source") or ""), "label": label, "reason": str(decision.reason), "text": str(passage.get("text") or "")})
        if label == "keep":
            kept.append(passage)
    return {"grades": grades, "graded": kept}


# BREAK: make your grade keep every passage. Change
#     if label == "keep":
# to
#     if label:
# run the lab, then python -m pytest tests/test_lab_08_03_03.py -q and read the red line.
# git checkout -- labs/08_03_03_agentic_rag_graph.py puts it back.


# %%
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
graph = build_rag_graph(model=chat, grade_fn=grade)
drawn = graph.get_graph()
print("nodes", [name for name in drawn.nodes if not name.startswith("__")])
print("edges", [f"{edge.source} -> {edge.target}" for edge in drawn.edges])


def run(graph, question: str, desk: str) -> dict:
    print("desk", desk)
    print("question", question)
    started = time.perf_counter()
    state = graph.invoke({"question": question})
    seconds = time.perf_counter() - started
    print("route", state.get("route"))
    for passage in state.get("passages") or []:
        print("retrieved", round(float(passage.get("score", 0)), 4), passage.get("source"))
    for row in state.get("grades") or []:
        print("GRADE", row["label"], row["source"], "|", row["reason"])
    print("answer", state.get("answer"))
    cited = [row.get("source") for row in state.get("sources") or []]
    print("sources", cited)
    print("handbook_retrieved", any("employee_handbook" in str(p.get("source")) for p in state.get("passages") or []))
    print("cited_handbook", any("employee_handbook" in str(source) for source in cited))
    print("grade_calls", len(state.get("grades") or []), "seconds", round(seconds, 1))
    return state


# %%
# The customer desk: the wiki and the customer facing pages only.
lamp = "Can I send back an unused lamp after twelve days?"
run(graph, lamp, "customer")


# %%
# The whole knowledge base, five passages, so the employee handbook can come back and meet your grade.
run(build_rag_graph(model=chat, grade_fn=grade, scope="all", retrieve_k=5), lamp, "all folders")
