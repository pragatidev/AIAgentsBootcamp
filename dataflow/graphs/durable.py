"""DataFlow durable desk: retries, a cached policy node, a receipt task, defer.

Side effects inside a node are wrapped as @task so a re-run after a crash
does not repeat a finished write. The carrier API is flaky on purpose.
The world is flaky there, not the model.
"""

from __future__ import annotations

import json
import operator
import os
import re
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import NodeError
from langgraph.func import task
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import CachePolicy, Command, RetryPolicy, Send

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext
from dataflow.tools.flaky import CarrierTimeout, fetch_carrier_status
from dataflow.tools.policy import search_policy

__all__ = [
    "CARRIER_LOG",
    "CRASH_AFTER_RECEIPT",
    "DurableState",
    "FAN_ITEMS",
    "FanState",
    "POLICY_CALLS",
    "POLICY_CACHE_TTL",
    "RECEIPTS_PATH",
    "build_durable",
    "build_two_length_fan",
    "count_receipts",
    "read_receipts",
    "reset_durable",
    "set_crash_after_receipt",
]

DATAFLOW = Path(__file__).resolve().parents[1]
RECEIPTS_PATH = DATAFLOW / "data" / "receipts.jsonl"
POLICY_CACHE_TTL = 30

SPEAK_SYSTEM = (
    "You write a DataFlow support reply. "
    "Write exactly two sentences. "
    "The first sentence names the carrier result, including a miss. "
    "The second sentence names the policy line the desk found. "
    "Do not invent an order or a policy that is not in the notes."
)

POLICY_CALLS = 0
CRASH_AFTER_RECEIPT = False
CARRIER_LOG: list[str] = []

FAN_ITEMS = [
    {"id": "alpha", "deep": False},
    {"id": "bravo", "deep": True},
    {"id": "charlie", "deep": False},
]


class DurableState(TypedDict, total=False):
    ticket: str
    order: dict[str, Any]
    carrier: dict[str, Any]
    log: Annotated[list, operator.add]
    reply: str
    policy: dict[str, Any]
    cache_hits: int


class PolicyInput(TypedDict):
    ticket: str


class ItemState(TypedDict, total=False):
    id: str
    deep: bool


class FanState(TypedDict, total=False):
    items: list
    results: Annotated[list, operator.add]
    runs: Annotated[list, operator.add]
    deep_items: Annotated[list, operator.add]


def reset_durable() -> None:
    """Reset lab counters and the planted crash flag."""
    global POLICY_CALLS, CRASH_AFTER_RECEIPT
    POLICY_CALLS = 0
    CRASH_AFTER_RECEIPT = False
    CARRIER_LOG.clear()


def set_crash_after_receipt(value: bool) -> None:
    global CRASH_AFTER_RECEIPT
    CRASH_AFTER_RECEIPT = bool(value)


def get_receipts_path() -> Path:
    env = os.environ.get("DATAFLOW_RECEIPTS_PATH", "").strip()
    if env:
        return Path(env)
    return Path(RECEIPTS_PATH)


def read_receipts() -> list[dict]:
    path = get_receipts_path()
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def count_receipts() -> int:
    return len(read_receipts())


def _content_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(p for p in parts if p)
    if content is None:
        return ""
    return str(content)


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


def _order_id(ticket: str) -> str:
    match = re.search(r"DF-\d+", (ticket or "").upper())
    return match.group(0) if match else ""


def _attempt_number(runtime: Runtime[DeskContext] | None) -> int:
    if runtime is not None:
        info = getattr(runtime, "execution_info", None)
        if info is not None:
            n = getattr(info, "node_attempt", None)
            if n is not None:
                return int(n)
    return len(CARRIER_LOG) + 1


def carrier_check(
    state: DurableState,
    runtime: Runtime[DeskContext] | None = None,
) -> dict[str, Any]:
    """Call the flaky carrier. RetryPolicy re-runs this on CarrierTimeout."""
    ticket = str(state.get("ticket") or "")
    order_id = _order_id(ticket)
    attempt = _attempt_number(runtime)
    if not order_id:
        line = f"attempt {attempt} skipped: no order id"
        CARRIER_LOG.append(line)
        return {
            "carrier": {"found": False, "reason": "no order id in the ticket"},
            "log": [line],
        }
    try:
        result = fetch_carrier_status.invoke({"order_id": order_id})
    except CarrierTimeout:
        line = f"attempt {attempt} timeout"
        CARRIER_LOG.append(line)
        raise
    line = f"attempt {attempt} success"
    CARRIER_LOG.append(line)
    return {
        "carrier": result,
        "order": result,
        "log": list(CARRIER_LOG),
    }


def carrier_error_handler(state: DurableState, error: NodeError) -> Command:
    """Typed miss after retries are exhausted, then continue to policy_search."""
    del error
    lines = list(CARRIER_LOG) or ["carrier unreachable after retries"]
    return Command(
        goto="policy_search",
        update={
            "carrier": {
                "found": False,
                "reason": "carrier unreachable after retries",
            },
            "log": lines,
        },
    )


def policy_search(state: PolicyInput) -> dict[str, Any]:
    """Keyword policy search. POLICY_CALLS proves a cache hit skipped this body."""
    global POLICY_CALLS
    POLICY_CALLS += 1
    ticket = str(state.get("ticket") or "")
    hit = search_policy.invoke({"question": ticket})
    return {"policy": hit}


@task
def write_receipt(ticket: str, order_id: str, status: str) -> dict:
    """Append one receipt row. A finished task is not repeated on resume."""
    row = {
        "ticket": ticket,
        "order_id": order_id,
        "status": status,
    }
    path = get_receipts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def send_receipt(state: DurableState) -> dict[str, Any]:
    """Call the receipt task, then optionally plant a crash after it finishes."""
    ticket = str(state.get("ticket") or "")
    carrier = dict(state.get("carrier") or {})
    order_id = str(carrier.get("order_id") or _order_id(ticket) or "")
    status = str(carrier.get("status") or carrier.get("reason") or "unknown")
    future = write_receipt(ticket, order_id, status)
    row = future.result() if hasattr(future, "result") else future
    if CRASH_AFTER_RECEIPT:
        raise RuntimeError("planted crash after the receipt task")
    return {"order": {"receipt": row}}


def speak(
    state: DurableState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, str]:
    chat = _resolve_chat(runtime, model)
    notes = (
        "Ticket:\n"
        + str(state.get("ticket") or "")
        + "\n\nCarrier:\n"
        + str(state.get("carrier") or {})
        + "\n\nPolicy line:\n"
        + str(state.get("policy") or {})
    )
    message = chat.invoke(
        [
            {"role": "system", "content": SPEAK_SYSTEM},
            {"role": "user", "content": notes},
        ]
    )
    return {"reply": _content_text(message)}


def build_durable(
    checkpointer=None,
    model=None,
    cache=None,
    cache_ttl: int = POLICY_CACHE_TTL,
):
    """Compile the durable desk. InMemorySaver and InMemoryCache by default."""
    if checkpointer is None:
        checkpointer = InMemorySaver()
    if cache is None:
        cache = InMemoryCache()

    def speak_node(
        state: DurableState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return speak(state, runtime=runtime, model=model)

    builder = StateGraph(DurableState, context_schema=DeskContext)
    builder.add_node(
        "carrier_check",
        carrier_check,
        retry_policy=RetryPolicy(
            max_attempts=3,
            initial_interval=0.2,
            backoff_factor=2.0,
            retry_on=CarrierTimeout,
        ),
        error_handler=carrier_error_handler,
    )
    builder.add_node(
        "policy_search",
        policy_search,
        input_schema=PolicyInput,
        cache_policy=CachePolicy(ttl=cache_ttl),
    )
    builder.add_node("send_receipt", send_receipt)
    builder.add_node("speak", speak_node)
    builder.add_edge(START, "carrier_check")
    builder.add_edge("carrier_check", "policy_search")
    builder.add_edge("policy_search", "send_receipt")
    builder.add_edge("send_receipt", "speak")
    builder.add_edge("speak", END)
    return builder.compile(checkpointer=checkpointer, cache=cache)


def load_items(state: FanState) -> dict[str, Any]:
    return {"items": list(FAN_ITEMS)}


def fan_items(state: FanState) -> list[Send]:
    return [Send("worker", item) for item in (state.get("items") or [])]


def worker(item: ItemState) -> Command:
    row = {"id": item.get("id"), "deep": bool(item.get("deep"))}
    if item.get("deep"):
        # Long branch writes after deep_check, so summarize without defer
        # sees only the short scores on its first run.
        return Command(goto="deep_check", update={"deep_items": [dict(item)]})
    return Command(goto="summarize", update={"results": [row]})


def deep_check(state: FanState) -> dict:
    """Extra hop on the long branch. This is why defer exists."""
    return {
        "results": [
            {"id": item.get("id"), "deep": True}
            for item in (state.get("deep_items") or [])
        ]
    }


def summarize(state: FanState) -> dict[str, list]:
    results = list(state.get("results") or [])
    return {"runs": [len(results)]}


def build_two_length_fan(model=None, defer: bool = True):
    """Three items, one long branch. defer waits for the long path.

    Branches of different lengths are the honest reason defer exists.
    model is unused: this graph does not think.
    """
    del model
    builder = StateGraph(FanState)
    builder.add_node("load", load_items)
    builder.add_node("worker", worker, destinations=("deep_check", "summarize"))
    builder.add_node("deep_check", deep_check)
    if defer:
        builder.add_node("summarize", summarize, defer=True)
    else:
        builder.add_node("summarize", summarize)
    builder.add_edge(START, "load")
    builder.add_conditional_edges("load", fan_items)
    builder.add_edge("deep_check", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()
