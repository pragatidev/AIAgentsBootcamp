"""DataFlow v2: classify returns Command instead of a conditional edge.

Same three desks as v2_route. The route and the next node
travel in one return.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from dataflow.graphs.v1_triage import DeskContext
from dataflow.graphs.v2_route import (
    TriageState,
    classify,
    escalate_desk,
    orders_desk,
    policy_desk,
)

ROUTE_TO_DESK = {
    "orders": "orders_desk",
    "policy": "policy_desk",
    "escalate": "escalate_desk",
}


def classify_command(
    state: TriageState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> Command:
    decision = classify(state, runtime=runtime, model=model)
    route = str(decision.get("route") or "escalate")
    dest = ROUTE_TO_DESK.get(route, "escalate_desk")
    return Command(goto=dest, update={"route": route})


def build_v2_command(*, model: Any = None):
    builder = StateGraph(TriageState, context_schema=DeskContext)

    def classify_node(
        state: TriageState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> Command:
        return classify_command(state, runtime=runtime, model=model)

    builder.add_node(
        "classify",
        classify_node,
        destinations=("orders_desk", "policy_desk", "escalate_desk"),
    )
    builder.add_node("orders_desk", orders_desk)
    builder.add_node("policy_desk", policy_desk)
    builder.add_node("escalate_desk", escalate_desk)
    builder.add_edge(START, "classify")
    builder.add_edge("orders_desk", END)
    builder.add_edge("policy_desk", END)
    builder.add_edge("escalate_desk", END)
    return builder.compile()
