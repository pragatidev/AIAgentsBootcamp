# %%
"""Lab 25.6: portfolio, DataFlow knowledge desk with FAISS retrieve.

What we build: you finish the DataFlow knowledge desk as something you can show: one function that runs a
ticket and returns the reply, the route, the files it cited and whether it refused; three tickets from the
question file that prove the three behaviours; and the desk's README, dataflow/README.md, which a test
keeps honest. This is the support-agent desk, scope "all": it may read the internal folders, so it answers
staff questions such as who may approve a refund. The customer desk is build_rag_graph() with the default
customer scope (lab 25.4).

What you learn: the block's ideas on one desk. 24.1's route (a lookup never searches), 25.1's citation (a
claim points at a file and a heading), 25.3's refusal (one fixed sentence when the grader empties the set),
and that cited nothing is not the same as refused. And Section 4's close again: a README is a contract a
test can check.

What will be true on your screen: the model off the object and desk support_agent scope all, then for each
ticket its route, cited sources, refused and retrieved, and the reply; then policy_cites_procedures True,
unknown_refused True, order_route lookup, order_retrieved False and order_refused False; then the desk's
tests by name with their pass line and pytest_exit 0.
"""

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.rag_graph import REFUSE_TEMPLATE, build_rag_graph
from eval.runners.rag_metrics import load_questions


# %%
# TYPE THIS: answer_question. The signature and docstring are given; you type the body.
# Its finished copy is answer_question in dataflow/graphs/rag_graph.py.
def answer_question(graph, text: str) -> dict:
    """Run one ticket through the knowledge desk. Return the reply, the route the desk chose, the source files it cited (in order, no repeats), whether it refused with the house sentence, and whether it retrieved any passages."""
    state = graph.invoke({"question": text})
    reply = str(state.get("reply") or "")
    sources = list(dict.fromkeys(str(row.get("source")) for row in state.get("sources") or [] if row.get("source")))
    return {
        "reply": reply,
        "route": state.get("route"),
        "sources": sources,
        "refused": reply.startswith(REFUSE_TEMPLATE.split(".")[0]),
        "retrieved": bool(state.get("passages")),
    }


# BREAK: write refused the way that reads right, as
#         "refused": not sources,
# run the lab and read order_refused, then python -m pytest tests/test_lab_08_04_06.py -q.
# git checkout -- labs/08_04_06_portfolio_knowledge_desk.py puts it back.


# %%
# Three tickets, read by id from the question file the evals score, so the lab and the evals share them.
rows = {row["id"]: row for row in load_questions()}
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("desk support_agent scope all")
graph = build_rag_graph(model=chat, scope="all")
results = {}
for qid in ("policy-refund", "refuse-coffee", "lookup-1002"):
    result = answer_question(graph, rows[qid]["question"])
    results[qid] = result
    print("ticket", qid, repr(rows[qid]["question"]))
    print("  route", result["route"], "sources", result["sources"], "refused", result["refused"], "retrieved", result["retrieved"])
    print("  " + result["reply"].replace("\n", "\n  "))


# %%
print("policy_cites_procedures", rows["policy-refund"]["expected_source"] in results["policy-refund"]["sources"])
print("unknown_refused", results["refuse-coffee"]["refused"])
print("order_route", results["lookup-1002"]["route"])
print("order_retrieved", results["lookup-1002"]["retrieved"])
print("order_refused", results["lookup-1002"]["refused"])


# %%
# The desk's tests, by name. None of them calls a model.
TESTS = [
    "tests/test_rag_load_chunk.py",
    "tests/test_rag_index_tool.py",
    "tests/test_rag_graph.py",
    "tests/test_rag_cite_refuse_eval.py",
    "tests/test_lab_08_04_06.py",
    "tests/test_dataflow_rag_readme.py",
]
if __name__ == "__main__":
    print("pytest_files", TESTS)
    done = subprocess.run([sys.executable, "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"], cwd=root, capture_output=True, text=True)
    print((done.stdout.strip().splitlines() or [""])[-1])
    print("pytest_exit", done.returncode)
