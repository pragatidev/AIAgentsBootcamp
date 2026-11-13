# %%
"""Lab 11.5: test routes with a scripted model.

What we build: you type one route test, here in this file. It sends three tickets through the routing desk
(build_v2_route), each with a scripted model that picks that ticket's route, and checks three things: the
route, the key the right desk wrote, and words only the right desk writes in the reply. The last cell runs
your test twice, once with the right routes and once with a scripted classifier that sends every ticket to
escalate, the way a broken prompt would. Then it runs the package's own route tests.

What you learn: a test is worth what it would catch. Yours fails when the route is wrong, and says which
ticket. A test that only checks there is a reply passes on a wrong route, because every desk writes a reply:
it passes for a reason that proves nothing. The scripted model (tests/fixtures/fake_model.py) is what
makes all of this run with no model and no network, which is why every later test in the course uses it.

What will be true on your screen: the model line (none: only the scripted model) and the versions, PASS for
your test with the right routes, FAIL with the ticket and the wrong route when every ticket is sent to
escalate, then the package's route tests passing and pytest_exit 0.
"""

from importlib.metadata import version
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.graphs.v2_route import build_v2_route
from tests.fixtures.fake_model import FakeChatModel

print("model none: every test here uses the scripted FakeChatModel")
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

# %%
# TYPE THIS: CASES and test_routes_are_right. The signature and docstring are given; you type the rest.
# The package's own route tests are test_route_orders, test_route_policy and test_route_escalate in
# tests/test_dataflow_routes.py. Each case: the ticket, its route, the key that route's desk writes, and
# words only that desk writes.
CASES = [
    ("Where is order DF-1001?", "orders", "order", "Order DF-1001 is"),
    ("What is your return window?", "policy", "policy", "From wiki/return_policy.md"),
    ("I want a manager on the phone today.", "escalate", "escalation", "Ticket parked for a human"),
]


def test_routes_are_right(make_model=FakeChatModel):
    """Every ticket with its own scripted model: the route, the key the desk wrote, the desk's own words."""
    for ticket, route, key, words in CASES:
        out = build_v2_route(model=make_model(route=route)).invoke({"ticket": ticket})
        assert out["route"] == route, (ticket, out["route"])
        assert key in out, (ticket, sorted(out))
        assert words in out["reply"], (ticket, out["reply"])


# BREAK: replace the three assert lines with the one line `        assert out["reply"]` and run. The run with
# every ticket sent to escalate now prints PASS: escalate wrote a reply for every ticket, so the test
# proves nothing about routes. Put the three asserts back and run.

# %%
def always_escalate(route: str) -> FakeChatModel:
    """A broken classifier: whatever the ticket, it says escalate."""
    return FakeChatModel(route="escalate")


for label, make_model in (("right routes", FakeChatModel), ("every ticket sent to escalate", always_escalate)):
    try:
        test_routes_are_right(make_model=make_model)
        print("PASS test_routes_are_right,", label)
    except AssertionError as err:
        print("FAIL test_routes_are_right,", label, err)

# %%
result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_dataflow_routes.py", "-q"], cwd=root, check=False)
print("pytest_exit", result.returncode)
