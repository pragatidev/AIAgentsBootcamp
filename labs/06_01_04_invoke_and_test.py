# %%
"""Lab 10.4: compile, invoke, and unit-test one node.

What we build: you type three tests, right here in this file: classify alone with a scripted model, lookup
alone on an order that does not exist, and the same classify node taken out of a freshly compiled graph. The
next cell runs your three tests and prints PASS or what failed. Then you send a real ticket through the
finished triage graph on your model and print every key of the state that comes back.

What you learn: a node is a plain function, so you test it with no graph, no model and no network: you hand
it a state and read what it returns. The model is injected (model=), which is the whole reason a node test
can run on a laptop with the model off. And the node the compiled graph holds is not quite the function
you wrote: it reads the run's runtime, and outside a run there is none.

What will be true on your screen: the model line and the versions, PASS test_classify_alone, PASS
test_lookup_miss and PASS test_classify_node_on_a_fresh_graph, then T-3001 through build_v1_triage with its
ticket, route, order and reply.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import pytest

import config
from dataflow.graphs.v1_triage import build_v1_triage, classify, lookup
from tests.fixtures.fake_model import FakeChatModel

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}

# %%
RETURN_WINDOW = by_id["T-3003"]["text"]
WHERE_IS = "Where is order DF-1002?"


# TYPE THIS: the three tests. The signatures and docstrings are given; you type the bodies.
# The package's own node tests are in tests/test_dataflow_v1.py.
def test_classify_alone():
    """classify by itself with a scripted model: no graph, no network."""
    out = classify({"ticket": RETURN_WINDOW}, model=FakeChatModel(route="policy"))
    assert out == {"route": "policy"}


def test_lookup_miss():
    """lookup by itself on an order that does not exist: the typed miss, not an exception."""
    out = lookup({"ticket": "Where is order DF-9999?"})
    assert out == {"order": {"found": False, "order_id": "DF-9999", "reason": "unknown order"}}


def test_classify_node_on_a_fresh_graph():
    """The node as a freshly built graph holds it. It reads the run's runtime, and outside a run there is none."""
    graph = build_v1_triage(model=FakeChatModel(route="orders"))
    with pytest.raises(ValueError, match="Missing required config key 'N/A' for 'classify'"):
        graph.nodes["classify"].invoke({"ticket": WHERE_IS})
    assert graph.nodes["lookup"].invoke({"ticket": WHERE_IS})["order"]["order_id"] == "DF-1002"


# BREAK: in test_classify_alone delete , model=FakeChatModel(route="policy") so classify finds no model and
# asks config for the real one. Stop Ollama (or set OLLAMA_BASE_URL=http://127.0.0.1:1 in .env) and run:
# test_classify_alone fails on the connection, not on its assert, while the two tests that need no model still
# pass; the real ticket at the end cannot run either, with the model off. That is why the model is injected.
# Put it back, start Ollama again and run.

# %%
for test in (test_classify_alone, test_lookup_miss, test_classify_node_on_a_fresh_graph):
    try:
        test()
        print("PASS", test.__name__)
    except (Exception, pytest.fail.Exception) as err:  # pytest.raises that saw no error raises pytest's own Failed
        print("FAIL", test.__name__, f"{type(err).__module__}.{type(err).__name__}: {err}")

# %%
# A real ticket through the finished graph on your model: every key of the state that comes back.
state = build_v1_triage(model=chat).invoke({"ticket": by_id["T-3001"]["text"]})
for key in ("ticket", "route", "order", "reply"):
    print(key, state.get(key))
