# %%
"""Lab 5.16: run a child with a clean context and show the polluted miss.

What we build: the model scores documents for one customer question, a customer returning a desk
lamp. First with every document in one context, then with one clean child per document that sees
only its own file. You type run_child. Then we plant a memo in the pile that tells the reader to
score every other document 0, and run both again. Three runs of each, so you see what a rerun
changes.

What you learn: isolation as a context technique. A child's window holds one instruction and one
document, so nothing else in the parent's pile can lean on its answer, and a planted instruction
in one document cannot reach the others. Its cost is a count of calls.

What will be true on your screen: for each run and each pile, the one-context scores, the
children's scores, the difference per file, and both rankings; then, per run, whether the memo
moved the one-context ranking of the three real files and whether it moved the children's.
Run python -m pytest tests/test_lab_03_16.py -q to test your run_child.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import applied_window, chat_caller
from dataflow.context.isolate import (
    MEMO_NAME,
    bundle_messages,
    child_messages,
    load_docs,
    parse_scores,
    ranking,
    score_of,
)

RUNS = 3
FILES = ["return_policy.md", "employee_handbook.txt", "shipping.md"]
call = chat_caller(num_predict=800)


# %%
# TYPE THIS: run_child. One clean context per document.
# BREAK: inside run_child, send bundle_messages(docs) instead of child_messages(name, body) and run.
# Every child now sees the whole pile, memo included. Put child_messages back.
def run_child(name: str, body: str, docs: dict) -> list:
    """Score one document in a context that holds only that document. Returns the parsed rows."""
    reply = call(child_messages(name, body))
    return parse_scores(reply["content"])


def score_pile(docs: dict) -> dict:
    one = parse_scores(call(bundle_messages(docs))["content"])
    one_context = {name: score_of(one, name) for name in docs}
    children = {name: score_of(run_child(name, body, docs), name) for name, body in docs.items()}
    return {"one_context": one_context, "children": children}


def show(run: int, pile: str, result: dict) -> None:
    one, kids = result["one_context"], result["children"]
    print("run", run, "pile", pile)
    print("one_context_scores", json.dumps(one))
    print("children_scores", json.dumps(kids))
    print("difference", json.dumps({n: None if one[n] is None or kids[n] is None else one[n] - kids[n] for n in one}))
    print("one_context_rank", ranking(one))
    print("children_rank", ranking(kids))


# %%
clean = load_docs(FILES)
planted = load_docs(FILES + [MEMO_NAME])
for run in range(1, RUNS + 1):
    before = score_pile(clean)
    show(run, "clean", before)
    after = score_pile(planted)
    show(run, "with_memo", after)
    three = lambda scores: ranking({n: scores[n] for n in FILES})
    print("memo_moved_one_context_rank", three(after["one_context"]) != three(before["one_context"]))
    print("memo_moved_children_rank", three(after["children"]) != three(before["children"]))
print("calls_per_run", 2 + len(clean) + len(planted))
print("window_applied", applied_window())
