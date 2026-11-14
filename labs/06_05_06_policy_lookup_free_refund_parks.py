# %%
"""Lab 14.5: policy: lookup is free, refund parks.

What we build: three tests that pin the DataFlow v4 desk's policy, typed here in the lab file. A lookup never
parks: it answers and nothing is left to run. A refund always parks at the refund node before any row is written.
And a partial run, the docs' way to test one branch: on a fresh checkpointer, update_state(..., as_node="classify")
writes the state as if classify had just run with route refund, then invoke(None, ..., interrupt_after=["refund"])
runs from there and stops at the refund node's own interrupt(). The classifier is never asked. Then the same two
tickets go through the real model, and the last cell runs the package's own human-in-the-loop tests.

What you learn: a pause is a policy, and a policy needs a test that would fail if someone broke it. Each test gets
its own InMemorySaver, so no thread leaks from one test into the next. The partial run tests the refund road on its
own: the model in that test is scripted to say lookup, so if the classifier were ever asked the ticket would go the
wrong way and the test would fail. interrupt_after is a static breakpoint: the docs keep those for tests and
debugging, and keep interrupt() for the real pause.

What will be true on your screen: the model line (the scripted FakeChatModel in the tests, the real one for the
tickets) and the versions; PASS for test_lookup_never_parks, test_refund_always_parks and test_refund_road_alone;
then T-3002 routed lookup with its reply and nothing left to run, and T-3001 routed refund, parked at ('refund',)
with the reviewer's question and no refund row; then the package's tests passing and pytest_exit 0.
"""

from importlib.metadata import version
from pathlib import Path
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.checkpoint.memory import InMemorySaver

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.refund import get_refunds_path, read_refunds
from tests.fixtures.fake_model import FakeChatModel

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {row["ticket_id"]: row for row in rows}
LOOKUP_TEXT = by_id["T-3002"]["text"]
REFUND_TEXT = by_id["T-3001"]["text"]

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()


# %%
# TYPE THIS: the three tests. The names and docstrings are given; you type the rest.
# The package's own tests of the same policy are test_lookup_does_not_park, test_refund_parks and
# test_static_interrupt_before_refund in tests/test_dataflow_hitl.py.
def test_lookup_never_parks():
    """A lookup ticket runs straight through: a reply, no pause, nothing left to run."""
    graph = build_v4_hitl(checkpointer=InMemorySaver(), model=FakeChatModel(route="lookup"))
    config = {"configurable": {"thread_id": "policy-lookup"}}
    out = graph.invoke({"ticket": LOOKUP_TEXT}, config)
    assert "__interrupt__" not in out, out["__interrupt__"]
    assert graph.get_state(config).next == ()
    assert out["reply"].startswith("looked up DF-1002."), out["reply"]


def test_refund_always_parks():
    """A refund ticket parks at the refund node before any row is written."""
    graph = build_v4_hitl(checkpointer=InMemorySaver(), model=FakeChatModel(route="refund"))
    config = {"configurable": {"thread_id": "policy-refund"}}
    out = graph.invoke({"ticket": REFUND_TEXT}, config)
    assert graph.get_state(config).next == ("refund",), out.get("reply")
    assert out["__interrupt__"][0].value["order_id"] == "DF-1001"
    assert read_refunds() == []


def test_refund_road_alone():
    """A partial run: start after classify with route refund, stop at refund. The classifier is never asked."""
    graph = build_v4_hitl(checkpointer=InMemorySaver(), model=FakeChatModel(route="lookup"))
    config = {"configurable": {"thread_id": "policy-partial"}}
    graph.update_state(config, {"ticket": REFUND_TEXT, "route": "refund"}, as_node="classify")
    out = graph.invoke(None, config, interrupt_after=["refund"])
    assert out["__interrupt__"][0].value["amount"] == 49.0, out.get("reply")
    assert graph.get_state(config).next == ("refund",)
    assert read_refunds() == []


# BREAK: in test_refund_always_parks, change route="refund" to route="lookup", the way a classifier with a broken
# prompt would send a refund straight to the lookup desk, and run. The test prints FAIL with the reply the lookup
# desk wrote ("looked up DF-1001. ..."): the refund never reached the pause. Put it back and run.

# %%
for test in (test_lookup_never_parks, test_refund_always_parks, test_refund_road_alone):
    try:
        test()
        print("PASS", test.__name__)
    except AssertionError as err:
        print("FAIL", test.__name__, err)

# %%
graph = build_v4_hitl(model=chat)
for ticket_id in ("T-3002", "T-3001"):
    thread = {"configurable": {"thread_id": "lab-14-5-" + ticket_id}}
    out = graph.invoke({"ticket": by_id[ticket_id]["text"]}, thread)
    state = graph.get_state(thread)
    print("ticket", ticket_id, "route", out.get("route"), "next", state.next)
    print("reply", out.get("reply"))
    for item in state.interrupts:
        print("question", item.value["question"])
print("refunds_rows", len(read_refunds()))

# %%
sys.stdout.flush()  # the lines above reach the screen before pytest's own output
result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_dataflow_hitl.py", "-q"], cwd=root, check=False)
print("pytest_exit", result.returncode)
