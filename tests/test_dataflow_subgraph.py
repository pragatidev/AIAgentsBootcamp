"""6.7 DataFlow billing subgraph. Pytest stays green with no live model."""

from langgraph.types import Command

from dataflow.graphs.billing_subgraph import (
    build_billing_graph,
    build_desk_with_billing,
)
from tests.fixtures.fake_model import FakeChatModel

TICKET_3012 = "My invoice for DF-1023 is missing the tax line. Can you resend it?"
TICKET_3005 = "You billed me twice for order DF-1010. Please reverse the extra charge."


def _thread(name: str) -> dict:
    return {"configurable": {"thread_id": name}}


def _billing_model(*, duplicate_charge: bool) -> FakeChatModel:
    return FakeChatModel(
        route="billing",
        reply="The invoice for DF-1023 is missing a tax line. No adjustment is due.",
        structured={
            "BillingFinding": {
                "duplicate_charge": duplicate_charge,
                "missing_tax_line": not duplicate_charge,
                "disputed_fee": False,
            }
        },
    )


def test_subgraph_private_state():
    model = _billing_model(duplicate_charge=False)
    sub = build_billing_graph(model=model)
    sub_out = sub.invoke({"ticket": TICKET_3012})
    assert "invoice" in sub_out
    assert "adjustment" in sub_out
    parent = build_desk_with_billing(model=model)
    parent_out = parent.invoke({"ticket": TICKET_3012}, _thread("test-13-6-private"))
    assert "invoice" not in parent_out
    assert "adjustment" not in parent_out
    assert parent_out.get("reply")


def test_subgraph_interrupt_parks_parent():
    model = _billing_model(duplicate_charge=True)
    graph = build_desk_with_billing(model=model)
    cfg = _thread("test-13-6-park")
    graph.invoke({"ticket": TICKET_3005}, cfg)
    state = graph.get_state(cfg)
    assert state.interrupts
    payload = state.interrupts[0].value
    assert payload["action"] == "adjust"
    assert payload["order_id"] == "DF-1010"
    assert payload["amount"] == 22.0
    done = graph.invoke(Command(resume="approve"), cfg)
    assert "approved" in (done.get("reply") or "")
    assert "DF-1010" in (done.get("reply") or "")


def test_subgraph_checkpointer_false_behaviour():
    """langgraph 1.2.11: False does not raise. The parent still parks."""
    model = _billing_model(duplicate_charge=True)
    graph = build_desk_with_billing(model=model, subgraph_checkpointer=False)
    cfg = _thread("test-13-6-false")
    out = graph.invoke({"ticket": TICKET_3005}, cfg)
    state = graph.get_state(cfg)
    assert out.get("__interrupt__")
    assert state.interrupts
    assert "billing" in tuple(state.next)
    assert out.get("reply") is None
