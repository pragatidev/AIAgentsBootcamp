"""Park a DataFlow MCP refund. The graph holds the gate. The tool writes.

interrupt() runs before the bound MCP refund tool. Resume with
Command(resume={"approve": bool}).
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from dataflow.mcp.bind import bind_mcp_tools
from dataflow.mcp.runtime import run_async


class GatedState(TypedDict, total=False):
    order_id: str
    amount: float
    reason: str
    refund: dict
    reply: str
    decision: Any


def _as_dict(result: Any) -> dict:
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        for block in result:
            if isinstance(block, dict) and block.get("type") == "text":
                text = str(block.get("text") or "")
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}
                if isinstance(parsed, dict):
                    return parsed
                return {"raw": parsed}
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return {"raw": result}
        if isinstance(parsed, dict):
            return parsed
    return {"raw": str(result)}


def _approve(decision: Any) -> bool:
    if isinstance(decision, dict):
        if "approve" in decision:
            return bool(decision.get("approve"))
        raw = decision.get("action") or decision.get("decision") or ""
        return str(raw).strip().lower() == "approve"
    return str(decision).strip().lower() in {"approve", "true", "yes"}


def _pick_refund_tool(tools: list[Any]) -> Any:
    for tool in tools:
        if str(getattr(tool, "name", "")) == "refund":
            return tool
    raise LookupError("bound tools have no refund")


def _call_bound(tool: Any, args: dict[str, Any]) -> Any:
    """Call a bound MCP tool from a sync graph node.

    Wrapped tools (bind wrap=True) have a sync func that hops onto the
    long-lived MCP loop. Raw MCPAdapter tools are async only.
    """
    if getattr(tool, "func", None) is not None:
        return tool.invoke(args)
    ainvoke = getattr(tool, "ainvoke", None)
    if ainvoke is not None:
        return run_async(ainvoke(args))
    return tool.invoke(args)


def build_gated_mcp(
    *,
    model: Any = None,
    tools: list[Any] | None = None,
    checkpointer: Any = None,
    target: Any = None,
):
    """Compile the gated refund graph. model is accepted so tests can pass a fixture."""
    del model
    if tools is None:
        tools = bind_mcp_tools(target)
    refund_tool = _pick_refund_tool(tools)

    def refund_node(state: GatedState) -> dict[str, Any]:
        order_id = str(state.get("order_id") or "")
        amount = float(state.get("amount") or 0)
        reason = str(state.get("reason") or "")
        payload = {
            "action": "refund",
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
        }
        decision = interrupt(payload)
        if not _approve(decision):
            return {
                "decision": decision,
                "refund": {
                    "refunded": False,
                    "declined": True,
                    "order_id": order_id,
                    "reason": "reviewer denied",
                },
                "reply": "Refund declined for order " + order_id,
            }
        args = {
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
        }
        raw = _call_bound(refund_tool, args)
        record = _as_dict(raw)
        return {
            "decision": decision,
            "refund": record,
            "reply": "Refund issued for order " + order_id,
        }

    builder = StateGraph(GatedState)
    builder.add_node("refund", refund_node)
    builder.add_edge(START, "refund")
    builder.add_edge("refund", END)
    kwargs: dict[str, Any] = {}
    if checkpointer is not False:
        kwargs["checkpointer"] = (
            InMemorySaver() if checkpointer is None else checkpointer
        )
    return builder.compile(**kwargs)


def resume_gated(graph: Any, config: dict[str, Any], approve: bool) -> Any:
    return graph.invoke(Command(resume={"approve": approve}), config)
