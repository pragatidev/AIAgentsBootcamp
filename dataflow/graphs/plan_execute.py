"""DataFlow plan and execute. Two nodes. Plan names tools, execute runs only those."""

from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext
from dataflow.tools.orders import lookup_order_by_id
from dataflow.tools.policy import search_policy_docs
from dataflow.tools.retrieve import retrieve_passages

__all__ = [
    "DeskTool",
    "Plan",
    "PlanExecuteState",
    "PlanStep",
    "build_plan_execute",
    "build_plan_execute_planted",
    "execute",
    "plan",
]

DeskTool = Literal[
    "lookup_order_by_id",
    "lookup_order",
    "retrieve",
    "decline_refund",
    "issue_refund",
    "search_policy",
]

LOOKUP_NAMES = frozenset(
    {"lookup_order_by_id", "lookup_order", "lookup_order_tool"}
)

CANON = {
    "lookup_order_by_id": "lookup_order_by_id",
    "lookup_order": "lookup_order_by_id",
    "lookup_order_tool": "lookup_order_by_id",
    "retrieve": "retrieve",
    "decline_refund": "decline_refund",
    "issue_refund": "issue_refund",
    "search_policy": "search_policy",
}

PLAN_SYSTEM = (
    "You write a plan for a DataFlow billing ticket. "
    "Return a list of steps. Each step names one tool and why. "
    "Allowed tools: lookup_order_by_id, retrieve, decline_refund, "
    "issue_refund, search_policy. "
    "issue_refund parks for a person; it does not write. "
    "A duplicate charge usually needs lookup_order_by_id then retrieve. "
    "Name the tools before any tool runs. Do not invent a tool."
)


class PlanExecuteState(TypedDict, total=False):
    ticket: str
    plan: dict[str, Any]
    trace: list


class PlanStep(BaseModel):
    tool: DeskTool = Field(description="Desk tool this step will call")
    why: str = Field(description="One short reason for this step")


class Plan(BaseModel):
    steps: list[PlanStep] = Field(description="Tools to run, in order")


def _resolve_chat(
    runtime: Runtime[DeskContext] | None,
    model: Any,
) -> Any:
    chat = model
    if chat is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        chat = getattr(ctx, "model", None) if ctx is not None else None
    if chat is None:
        chat = get_chat_model()
    return chat


def _order_id_from_ticket(ticket: str) -> str:
    match = re.search(r"DF-\d+", (ticket or "").upper())
    return match.group(0) if match else ""


def _plan_payload(decision: Any) -> dict[str, Any]:
    if decision is None:
        return {"steps": []}
    if hasattr(decision, "model_dump"):
        return decision.model_dump()
    if isinstance(decision, dict):
        steps = decision.get("steps") or []
        return {"steps": list(steps)}
    steps = getattr(decision, "steps", []) or []
    rows = []
    for item in steps:
        if hasattr(item, "model_dump"):
            rows.append(item.model_dump())
        elif isinstance(item, dict):
            rows.append(dict(item))
        else:
            rows.append(
                {
                    "tool": str(getattr(item, "tool", "")),
                    "why": str(getattr(item, "why", "")),
                }
            )
    return {"steps": rows}


def _steps_of(plan: Any) -> list[dict[str, Any]]:
    if plan is None:
        return []
    if hasattr(plan, "model_dump"):
        plan = plan.model_dump()
    if not isinstance(plan, dict):
        return []
    rows = []
    for item in plan.get("steps") or []:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "tool": str(item.get("tool") or ""),
                "why": str(item.get("why") or ""),
            }
        )
    return rows


def _planned_names(steps: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for step in steps:
        raw = str(step.get("tool") or "").strip()
        names.add(raw)
        names.add(CANON.get(raw, raw))
    return names


def _summarize(result: Any) -> Any:
    if isinstance(result, dict):
        if "found" in result:
            return {
                "found": result.get("found"),
                "order_id": result.get("order_id"),
                "item": result.get("item"),
                "status": result.get("status"),
                "reason": result.get("reason"),
            }
        if "parked" in result or "declined" in result or "refunded" in result:
            keep = {}
            for key in (
                "parked",
                "action",
                "refunded",
                "declined",
                "order_id",
                "reason",
            ):
                if key in result:
                    keep[key] = result[key]
            return keep
        if "paragraph" in result or "path" in result:
            para = str(result.get("paragraph") or result.get("reason") or "")
            return {"path": result.get("path"), "paragraph": para[:160]}
        return {key: result[key] for key in list(result)[:6]}
    if isinstance(result, list):
        first = result[0] if result else {}
        source = ""
        if isinstance(first, dict):
            source = str(first.get("source") or first.get("path") or "")
        return {"n": len(result), "source": source}
    return str(result)[:200]


def _blocked(name: str) -> dict[str, Any]:
    return {"tool": name, "blocked": True, "reason": "not in plan"}


def _run_tool(name: str, why: str, ticket: str) -> dict[str, Any]:
    canon = CANON.get(name, name)
    order_id = _order_id_from_ticket(ticket)
    if canon == "lookup_order_by_id":
        args = {"order_id": order_id or ticket}
        result = lookup_order_by_id(order_id or ticket)
        return {"tool": "lookup_order_by_id", "args": args, "result": _summarize(result)}
    if canon == "retrieve":
        args = {"question": ticket, "k": 3}
        result = retrieve_passages(ticket, k=3)
        return {"tool": "retrieve", "args": args, "result": _summarize(result)}
    if canon == "search_policy":
        args = {"question": ticket}
        result = search_policy_docs(ticket)
        return {"tool": "search_policy", "args": args, "result": _summarize(result)}
    if canon == "decline_refund":
        from dataflow.tools.refund import decline_refund

        args = {
            "order_id": order_id,
            "reason": why or "planned decline",
        }
        result = decline_refund.invoke(args)
        return {"tool": "decline_refund", "args": args, "result": _summarize(result)}
    if canon == "issue_refund":
        args = {
            "order_id": order_id,
            "reason": why or "planned refund",
        }
        result = {
            "parked": True,
            "action": "refund",
            "order_id": order_id,
            "reason": "planned refund waits for confirm",
        }
        return {"tool": "issue_refund", "args": args, "result": _summarize(result)}
    return _blocked(name)


def plan(state, runtime=None, *, model=None):
    """Call the model from config. Return a structured plan with tools named."""
    chat = _resolve_chat(runtime, model)
    structured = chat.with_structured_output(Plan)
    ticket = str(state.get("ticket") or "")
    decision = structured.invoke(
        [
            {"role": "system", "content": PLAN_SYSTEM},
            {"role": "user", "content": ticket},
        ]
    )
    return {"plan": _plan_payload(decision)}


def execute(state, *, plant_unplanned_lookup: bool = False):
    """Run planned tools in order. An unplanned call is a typed miss.

    plant_unplanned_lookup is the lab break: lookup runs when the ticket
    names an order id even if the plan did not name it.
    """
    ticket = str(state.get("ticket") or "")
    steps = _steps_of(state.get("plan"))
    planned = _planned_names(steps)
    trace: list[dict[str, Any]] = []
    for step in steps:
        raw = str(step.get("tool") or "").strip()
        why = str(step.get("why") or "")
        if not raw:
            continue
        if raw not in CANON and CANON.get(raw, raw) not in CANON:
            trace.append(_blocked(raw))
            continue
        if raw not in planned and CANON.get(raw, raw) not in planned:
            trace.append(_blocked(CANON.get(raw, raw)))
            continue
        trace.append(_run_tool(raw, why, ticket))
    order_id = _order_id_from_ticket(ticket)
    lookup_planned = bool(planned.intersection(LOOKUP_NAMES))
    if order_id and not lookup_planned:
        if plant_unplanned_lookup:
            # Planted miss for the lab: run lookup even when the plan did not name it.
            result = lookup_order_by_id(order_id)
            trace.append(
                {
                    "tool": "lookup_order_by_id",
                    "args": {"order_id": order_id},
                    "result": _summarize(result),
                }
            )
        else:
            trace.append(_blocked("lookup_order_by_id"))
    return {"trace": trace}


def build_plan_execute(model=None, plant_unplanned_lookup: bool = False):
    builder = StateGraph(PlanExecuteState, context_schema=DeskContext)

    def plan_node(
        state: PlanExecuteState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return plan(state, runtime=runtime, model=model)

    def execute_node(state: PlanExecuteState) -> dict[str, Any]:
        return execute(state, plant_unplanned_lookup=plant_unplanned_lookup)

    builder.add_node("plan", plan_node)
    builder.add_node("execute", execute_node)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "execute")
    builder.add_edge("execute", END)
    return builder.compile()


def build_plan_execute_planted(model=None):
    """Second builder. Execute calls lookup on its own when the ticket names an id."""
    return build_plan_execute(model=model, plant_unplanned_lookup=True)
