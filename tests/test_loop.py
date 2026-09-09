"""S7.4 class matches the fixture loop."""

from northstar.agent.loop import AgentLoop, run_loop
from northstar.tools.escalate import escalate_to_human
from northstar.tools.orders import lookup_order
from northstar.tools.policy import read_policy

TOOLS = {
    "orders": lookup_order,
    "policy": read_policy,
    "escalate": escalate_to_human,
}


def test_class_matches_function():
    ticket = "Can I return order NS-1001?"
    a = run_loop(ticket, TOOLS)
    b = AgentLoop(TOOLS).run(ticket)
    assert a["ticket"] == b["ticket"]
    assert [s["action"] for s in a["steps"]] == [s["action"] for s in b["steps"]]
