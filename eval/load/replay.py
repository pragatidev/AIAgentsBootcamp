"""Replay eval/golden.jsonl through the DataFlow desk under load.

Prints tickets per minute, p95 latency, tokens per ticket, and a spend
column derived from tokens. Tokens, not a price.
"""

from __future__ import annotations

import argparse
import math
import os
import threading
import time
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool

from config import get_chat_model
from dataflow.graphs.rag_tool_cycle import DESK_TOOLS, build_rag_tool_cycle
from eval.runners.golden import GOLDEN, load_golden


def p95(values: list[float]) -> float:
    """Ninety fifth percentile. The tail the slow customer feels, not the mean."""
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    rank = max(1, int(math.ceil(0.95 * len(ordered))))
    return ordered[rank - 1]


def tokens_of(message: Any) -> tuple[int, str]:
    """Read total_tokens from usage_metadata. 0 and a why if the model reports none."""
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict) and usage.get("total_tokens") is not None:
        return int(usage["total_tokens"]), "usage_metadata.total_tokens"
    if usage is not None:
        total = getattr(usage, "total_tokens", None)
        if total is not None:
            return int(total), "usage_metadata.total_tokens"
    meta = getattr(message, "response_metadata", None) or {}
    if isinstance(meta, dict):
        nested = meta.get("token_usage") or meta.get("usage") or {}
        if isinstance(nested, dict) and nested.get("total_tokens") is not None:
            return int(nested["total_tokens"]), "response_metadata.total_tokens"
        if nested.get("prompt_tokens") is not None or nested.get("completion_tokens") is not None:
            inp = int(nested.get("prompt_tokens") or nested.get("input_tokens") or 0)
            out = int(nested.get("completion_tokens") or nested.get("output_tokens") or 0)
            return inp + out, "response_metadata prompt+completion"
    return (
        0,
        "model reported no usage_metadata; tokens=0",
    )


def last_ai_message(result: Any) -> Any:
    messages = []
    if isinstance(result, dict):
        messages = list(result.get("messages") or [])
    for item in reversed(messages):
        kind = str(getattr(item, "type", "") or item.__class__.__name__).lower()
        if "ai" in kind or "assistant" in kind:
            return item
    return messages[-1] if messages else None


def token_rate() -> float:
    raw = os.environ.get("DATAFLOW_TOKEN_RATE", "0").strip() or "0"
    try:
        return float(raw)
    except ValueError:
        return 0.0


def wrap_slow_once(
    tool: Any, seconds: float, cancel: threading.Event | None = None
) -> Any:
    """Sleep on the first call only so one ticket hangs and the rest finish."""
    inner = getattr(tool, "func", None) or getattr(tool, "_run", None)
    fired = {"done": False}

    def sleepy(*args: Any, **kwargs: Any) -> Any:
        if not fired["done"]:
            fired["done"] = True
            deadline = time.perf_counter() + float(seconds)
            while time.perf_counter() < deadline:
                if cancel is not None and cancel.is_set():
                    break
                time.sleep(0.05)
        if inner is None:
            return tool.invoke(kwargs or (args[0] if args else {}))
        return inner(*args, **kwargs)

    return StructuredTool.from_function(
        func=sleepy,
        name=getattr(tool, "name", "tool"),
        description=getattr(tool, "description", "") or "tool",
        args_schema=getattr(tool, "args_schema", None),
    )


def _run_one(
    row: dict[str, Any],
    *,
    model: Any,
    tools: list[Any],
) -> dict[str, Any]:
    graph = build_rag_tool_cycle(model=model, tools=tools)
    started = time.perf_counter()
    result = graph.invoke(
        {"messages": [HumanMessage(content=str(row.get("input") or ""))]}
    )
    seconds = time.perf_counter() - started
    message = last_ai_message(result)
    tokens, why = tokens_of(message)
    rate = token_rate()
    return {
        "id": row.get("id"),
        "seconds": seconds,
        "tokens": tokens,
        "spend": tokens * rate,
        "status": "ok",
        "tokens_why": why,
    }


def run_replay(
    *,
    rows: list[dict[str, Any]] | None = None,
    model: Any = None,
    concurrency: int = 4,
    timeout: float | None = 60.0,
    slow_node: bool = False,
    slow_seconds: float | None = None,
    tools: list[Any] | None = None,
    progress: bool = True,
) -> dict[str, Any]:
    """Fan golden tickets through the desk. timeout=None never marks HUNG."""
    rows = list(rows) if rows is not None else load_golden(GOLDEN)
    chat = model if model is not None else get_chat_model()
    tool_list = list(tools) if tools is not None else list(DESK_TOOLS)
    cancel = threading.Event()
    if slow_node:
        wait_s = slow_seconds
        if wait_s is None:
            wait_s = (float(timeout) + 5.0) if timeout is not None else 70.0
        wrapped = False
        new_tools = []
        for tool in tool_list:
            name = str(getattr(tool, "name", "") or "")
            if not wrapped and name in {"retrieve", "lookup_order"}:
                new_tools.append(wrap_slow_once(tool, wait_s, cancel))
                wrapped = True
            else:
                new_tools.append(tool)
        if not wrapped and new_tools:
            new_tools[0] = wrap_slow_once(new_tools[0], wait_s, cancel)
        tool_list = new_tools
    if progress:
        print("tickets", len(rows), flush=True)
        print("concurrency", concurrency, flush=True)
        print("timeout", timeout, flush=True)
        print("slow_node", bool(slow_node), flush=True)
        print(
            "spend column is tokens times DATAFLOW_TOKEN_RATE, default 0",
            flush=True,
        )

    results: list[dict[str, Any]] = []
    marked_hung: set[int] = set()
    sem = threading.Semaphore(max(1, int(concurrency)))

    class _Box:
        def __init__(self, row: dict[str, Any]) -> None:
            self.row = row
            self.started: float | None = None
            self.done = threading.Event()
            self.item: dict[str, Any] | None = None
            self.exc: Exception | None = None

    def worker(box: _Box) -> None:
        sem.acquire()
        box.started = time.perf_counter()
        try:
            box.item = _run_one(box.row, model=chat, tools=tool_list)
        except Exception as exc:
            box.exc = exc
        finally:
            sem.release()
            box.done.set()

    boxes = [_Box(row) for row in rows]
    for box in boxes:
        threading.Thread(target=worker, args=(box,), daemon=True).start()
    remaining = set(boxes)
    try:
        while remaining:
            time.sleep(0.25)
            now = time.perf_counter()
            for box in list(remaining):
                if box.done.is_set():
                    remaining.discard(box)
                    if id(box) in marked_hung:
                        continue
                    row = box.row
                    if box.exc is not None:
                        item = {
                            "id": row.get("id"),
                            "seconds": (
                                now - box.started if box.started else 0.0
                            ),
                            "tokens": 0,
                            "spend": 0.0,
                            "status": "ERROR",
                            "tokens_why": str(box.exc),
                        }
                    else:
                        item = box.item or {
                            "id": row.get("id"),
                            "seconds": 0.0,
                            "tokens": 0,
                            "spend": 0.0,
                            "status": "ERROR",
                            "tokens_why": "no result",
                        }
                    results.append(item)
                    if progress:
                        print(
                            "row",
                            item.get("id"),
                            item.get("status"),
                            "seconds",
                            round(float(item.get("seconds") or 0), 2),
                            flush=True,
                        )
                    continue
                if (
                    timeout is not None
                    and box.started is not None
                    and (now - box.started) >= float(timeout)
                ):
                    remaining.discard(box)
                    marked_hung.add(id(box))
                    item = {
                        "id": box.row.get("id"),
                        "seconds": float(timeout),
                        "tokens": 0,
                        "spend": 0.0,
                        "status": "HUNG",
                        "tokens_why": "ticket did not return before timeout",
                    }
                    results.append(item)
                    if progress:
                        print("row", item["id"], "HUNG", flush=True)
                    cancel.set()
    finally:
        cancel.set()

    finished = [r for r in results if r.get("status") == "ok"]
    latencies = [float(r["seconds"]) for r in finished]
    wall = sum(float(r.get("seconds") or 0) for r in finished) / max(
        1, int(concurrency)
    )
    if finished:
        tickets_per_minute = len(finished) / max(wall / 60.0, 1e-9)
    else:
        tickets_per_minute = 0.0
    tokens_list = [int(r.get("tokens") or 0) for r in finished]
    tokens_per_ticket = (
        sum(tokens_list) / len(tokens_list) if tokens_list else 0.0
    )
    spend_per_ticket = tokens_per_ticket * token_rate()
    p95_s = p95(latencies)
    whys = {str(r.get("tokens_why") or "") for r in results}
    report = {
        "rows": results,
        "tickets_per_minute": tickets_per_minute,
        "p95": p95_s,
        "tokens_per_ticket": tokens_per_ticket,
        "spend_per_ticket": spend_per_ticket,
        "token_whys": sorted(whys),
    }
    return report


def print_table(report: dict[str, Any]) -> None:
    print("ticket id seconds tokens spend status", flush=True)
    for row in report.get("rows") or []:
        extra = ""
        if row.get("status") == "ERROR":
            extra = " " + str(row.get("tokens_why") or "")
        print(
            row.get("id"),
            round(float(row.get("seconds") or 0), 3),
            int(row.get("tokens") or 0),
            round(float(row.get("spend") or 0), 6),
            row.get("status"),
            extra,
            flush=True,
        )
    print("tickets_per_minute", round(float(report["tickets_per_minute"]), 3), flush=True)
    print("p95", round(float(report["p95"]), 3), flush=True)
    print("tokens_per_ticket", round(float(report["tokens_per_ticket"]), 3), flush=True)
    print("spend_per_ticket", round(float(report["spend_per_ticket"]), 6), flush=True)
    print(
        "spend column is tokens times DATAFLOW_TOKEN_RATE, default 0",
        flush=True,
    )
    for why in report.get("token_whys") or []:
        if why and "no usage_metadata" in why:
            print("tokens_why", why, flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DataFlow load replay")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="per-ticket timeout in seconds. 0 means no timeout (suite can stall)",
    )
    parser.add_argument(
        "--slow-node",
        action="store_true",
        help="wrap one tool with a sleep longer than the timeout so a hang is real",
    )
    parser.add_argument(
        "--no-timeout",
        action="store_true",
        help="planted miss: no per-ticket timeout. The suite can stall.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    timeout: float | None = float(args.timeout)
    if args.no_timeout or timeout <= 0:
        timeout = None
    report = run_replay(
        concurrency=int(args.concurrency),
        timeout=timeout,
        slow_node=bool(args.slow_node),
    )
    print_table(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
