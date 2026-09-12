"""Importable UI logic for the DataFlow Streamlit desk.

The page only renders. Labs and tests call these functions. stream_tokens
yields (kind, payload) tuples: token, node, tool_call, interrupt.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from langgraph.types import Command

from dataflow.ambient.inbox import list_parked

__all__ = [
    "approve",
    "edit",
    "events_as_json",
    "inbox_rows",
    "reject",
    "reject_planted",
    "resolve_first",
    "run_blocking",
    "stream_tokens",
    "thread_config",
]


# Nodes whose model output is routing, not chat. Their tokens never reach the bubble.
ROUTING_NODES = {"classify"}


def thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": str(thread_id)}}


def _ticket_payload(ticket: Any) -> dict[str, Any]:
    if isinstance(ticket, dict) and "ticket" in ticket:
        return dict(ticket)
    return {"ticket": str(ticket)}


def _message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(p for p in parts if p)
    if content is None:
        return ""
    return str(content)


def _token_pieces(text: str) -> list[str]:
    body = str(text or "")
    if not body:
        return []
    words = body.split(" ")
    out: list[str] = []
    for i, word in enumerate(words):
        if i < len(words) - 1:
            out.append(word + " ")
        else:
            out.append(word)
    return out


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump())
        except Exception:
            return str(value)
    content = getattr(value, "content", None)
    if content is not None and not isinstance(value, (bytes, bytearray)):
        return _message_text(value)
    return str(value)


def events_as_json(events: list[tuple[str, Any]]) -> str:
    rows = [{"kind": kind, "payload": _jsonable(payload)} for kind, payload in events]
    return json.dumps(rows, indent=2)


def _part_type(part: Any) -> str | None:
    if isinstance(part, dict) and "type" in part:
        return str(part["type"])
    kind = getattr(part, "type", None)
    if kind:
        return str(kind)
    return None


def _part_data(part: Any) -> Any:
    if isinstance(part, dict) and "data" in part:
        return part["data"]
    data = getattr(part, "data", None)
    if data is not None:
        return data
    return part


def _tool_calls_from_message(message: Any) -> list[dict[str, Any]]:
    raw = getattr(message, "tool_calls", None) or []
    cards: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("tool") or "")
            args = item.get("args") if isinstance(item.get("args"), dict) else {}
        else:
            name = str(getattr(item, "name", "") or "")
            args = getattr(item, "args", None)
            args = args if isinstance(args, dict) else {}
        if name:
            cards.append({"name": name, "args": args})
    additional = getattr(message, "additional_kwargs", None) or {}
    if isinstance(additional, dict):
        fn_call = additional.get("function_call") or additional.get("tool_calls")
        if isinstance(fn_call, dict) and fn_call.get("name"):
            cards.append(
                {
                    "name": str(fn_call.get("name")),
                    "args": fn_call.get("arguments") or {},
                }
            )
    return cards


def _tool_card_from_update(node: str, update: Any, ticket: str) -> dict[str, Any] | None:
    if not isinstance(update, dict):
        return None
    if "order" in update and isinstance(update.get("order"), dict):
        order = update["order"]
        return {
            "name": "lookup_order",
            "args": {"order_id": order.get("order_id")},
        }
    if "policy" in update and isinstance(update.get("policy"), dict):
        return {
            "name": "search_policy",
            "args": {"question": ticket},
        }
    if node == "refund" and update.get("refund") is not None:
        refund = update.get("refund") or {}
        if isinstance(refund, dict):
            return {
                "name": "issue_refund",
                "args": {
                    "order_id": refund.get("order_id"),
                    "amount": refund.get("amount"),
                    "reason": refund.get("reason"),
                },
            }
    return None


def _tool_card_from_interrupt(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    action = str(payload.get("action") or "").strip()
    if not action:
        return None
    name = "issue_refund" if action == "refund" else action
    args = {}
    for key in ("order_id", "amount", "reason", "ticket"):
        if key in payload:
            args[key] = payload.get(key)
    return {"name": name, "args": args}


def _interrupt_values(graph: Any, cfg: dict[str, Any]) -> list[Any]:
    try:
        snap = graph.get_state(cfg)
    except Exception:
        return []
    items = getattr(snap, "interrupts", None) or ()
    out: list[Any] = []
    for item in items:
        out.append(item.value if hasattr(item, "value") else item)
    return out


def stream_tokens(
    graph: Any,
    ticket: Any,
    thread_id: str,
) -> Iterator[tuple[str, Any]]:
    """Yield UI events as the v4 HITL desk runs.

    messages mode feeds token. updates mode feeds node. A tool_call card
    is projected from tool messages, node outputs, or the park payload.
    The park comes from the state's interrupts after the stream ends, or
    from stream_events v3 when that projection is already populated.
    """
    cfg = thread_config(thread_id)
    payload = _ticket_payload(ticket)
    ticket_text = str(payload.get("ticket") or "")
    saw_token = False
    saw_tool = False

    stream = graph.stream(
        payload,
        cfg,
        stream_mode=["messages", "updates"],
        version="v2",
    )
    for part in stream:
        kind = _part_type(part)
        data = _part_data(part)
        if kind == "messages":
            message = data
            meta: dict[str, Any] = {}
            if isinstance(data, tuple) and len(data) == 2:
                message, meta = data
            node_name = str(meta.get("langgraph_node") or "") if isinstance(meta, dict) else ""
            if node_name in ROUTING_NODES:
                # classify is a structured routing call. Its JSON tokens are
                # for the graph, not the chat bubble.
                continue
            text = _message_text(message)
            if text:
                saw_token = True
                yield ("token", text)
            for card in _tool_calls_from_message(message):
                saw_tool = True
                yield ("tool_call", card)
            continue
        if kind == "updates" or (kind is None and isinstance(data, dict)):
            if not isinstance(data, dict):
                continue
            for node, update in data.items():
                name = str(node)
                if name.startswith("__"):
                    continue
                yield ("node", name)
                if isinstance(update, dict):
                    reply = update.get("reply")
                    if reply:
                        for piece in _token_pieces(str(reply)):
                            saw_token = True
                            yield ("token", piece)
                    card = _tool_card_from_update(name, update, ticket_text)
                    if card is not None:
                        saw_tool = True
                        yield ("tool_call", card)

    # Park: labs/06_06_03 read this off stream_events v3 as run.interrupts.
    # After a messages+updates stream the same projection is on the state.
    interrupts = _interrupt_values(graph, cfg)

    for value in interrupts:
        if not saw_tool:
            card = _tool_card_from_interrupt(value)
            if card is not None:
                saw_tool = True
                yield ("tool_call", card)
        yield ("interrupt", value)
        if not saw_token and isinstance(value, dict):
            question = value.get("question")
            if question:
                saw_token = True
                yield ("token", str(question))


def run_blocking(
    graph: Any,
    ticket: Any,
    thread_id: str = "blocking",
) -> Iterator[tuple[str, Any]]:
    """PLANTED: invoke waits until the graph finishes, then yields everything.

    Nothing is yielded while invoke is running. That is the blank page.
    """
    cfg = thread_config(thread_id)
    payload = _ticket_payload(ticket)
    result = graph.invoke(payload, cfg)
    values = result if isinstance(result, dict) else {}
    try:
        snap = graph.get_state(cfg)
        merged = dict(snap.values or {})
        for key, val in values.items():
            if not str(key).startswith("__"):
                merged[key] = val
        interrupts = [
            item.value if hasattr(item, "value") else item
            for item in (getattr(snap, "interrupts", None) or ())
        ]
    except Exception:
        merged = values
        interrupts = []

    if merged.get("route"):
        yield ("node", "classify")
    if merged.get("order") is not None:
        yield ("node", "lookup")
        order = merged.get("order") or {}
        if isinstance(order, dict):
            yield (
                "tool_call",
                {"name": "lookup_order", "args": {"order_id": order.get("order_id")}},
            )
    if merged.get("policy") is not None:
        yield ("node", "policy")
        yield (
            "tool_call",
            {
                "name": "search_policy",
                "args": {"question": str(merged.get("ticket") or "")},
            },
        )
    if merged.get("refund") is not None or interrupts:
        yield ("node", "refund")
    reply = merged.get("reply")
    if reply:
        yield ("token", str(reply))
    for value in interrupts:
        card = _tool_card_from_interrupt(value)
        if card is not None:
            yield ("tool_call", card)
        yield ("interrupt", value)


def _resume(graph: Any, thread_id: str, decision: Any) -> dict[str, Any]:
    cfg = thread_config(thread_id)
    result = graph.invoke(Command(resume=decision), cfg)
    values = result if isinstance(result, dict) else {}
    snap = graph.get_state(cfg)
    merged = dict(snap.values or {})
    for key, val in values.items():
        if not str(key).startswith("__"):
            merged[key] = val
    return {
        "thread_id": thread_id,
        "reply": merged.get("reply"),
        "refund": merged.get("refund"),
        "decision": merged.get("decision"),
        "actor": merged.get("actor"),
        "order": merged.get("order"),
    }


def approve(graph: Any, thread_id: str, actor: str = "reviewer") -> dict[str, Any]:
    """Resume a parked thread with yes. Returns the refund row."""
    return _resume(
        graph,
        thread_id,
        {"action": "approve", "actor": actor},
    )


def reject(
    graph: Any,
    thread_id: str,
    reason: str,
    actor: str = "reviewer",
) -> dict[str, Any]:
    """Resume with no plus a reason. Typed miss, no refund row."""
    return _resume(
        graph,
        thread_id,
        {"action": "reject", "reason": reason, "actor": actor},
    )


def reject_planted(
    graph: Any,
    thread_id: str,
    reason: str = "",
    actor: str = "reviewer",
) -> dict[str, Any]:
    """PLANTED: a reject that resumes with yes, so the write still happens."""
    return _resume(
        graph,
        thread_id,
        {"action": "approve", "actor": actor, "reason": reason},
    )


def edit(
    graph: Any,
    thread_id: str,
    payload: dict[str, Any],
    actor: str = "reviewer",
) -> dict[str, Any]:
    """Resume with the changed payload (amount or reason)."""
    decision: dict[str, Any] = {"action": "approve", "actor": actor}
    if payload:
        if "amount" in payload and payload["amount"] is not None:
            decision["amount"] = payload["amount"]
        if "reason" in payload and payload["reason"] is not None:
            decision["reason"] = payload["reason"]
    return _resume(graph, thread_id, decision)


def _age_seconds(parked_at: Any) -> float:
    import time
    from datetime import datetime

    now = time.time()
    if parked_at is None or parked_at == "":
        return 0.0
    if isinstance(parked_at, (int, float)):
        return max(0.0, now - float(parked_at))
    text = str(parked_at).strip()
    if not text:
        return 0.0
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return max(0.0, now - dt.timestamp())
    except ValueError:
        return 0.0


def inbox_rows(checkpointer: Any, graph: Any) -> list[dict[str, Any]]:
    """One row per parked thread: id, age in seconds, payload."""
    rows = list_parked(checkpointer, graph)
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "thread_id": row.get("thread_id"),
                "age_seconds": round(_age_seconds(row.get("parked_at")), 1),
                "payload": row.get("payload"),
                "ticket": row.get("ticket"),
                "parked_at": row.get("parked_at"),
            }
        )
    return out


def resolve_first(
    graph: Any,
    checkpointer: Any,
    answer: Any,
    actor: str = "reviewer",
) -> dict[str, Any]:
    """PLANTED: always resumes the first row's thread id, not the named one."""
    rows = inbox_rows(checkpointer, graph)
    if not rows:
        return {"thread_id": None, "reply": None, "refund": None}
    first_id = str(rows[0].get("thread_id") or "")
    text = str(answer).strip().lower() if not isinstance(answer, dict) else str(
        answer.get("action") or ""
    ).strip().lower()
    if text in {"reject", "deny", "no"}:
        reason = ""
        if isinstance(answer, dict):
            reason = str(answer.get("reason") or "")
        return reject(graph, first_id, reason or "planted first-row reject", actor=actor)
    return approve(graph, first_id, actor=actor)
