"""DataFlow v8: nightly triage. Clock door on the same desk.

Imports the v4 desk as a subgraph (invoked inside the worker on its own
thread), Send for the fan, a deferred report node, and the checkpointer
and store handed in at compile time.
"""

from __future__ import annotations

import json
import operator
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from dataflow.graphs.v4_hitl import build_v4_hitl

__all__ = [
    "NightlyState",
    "REPORTS_DIR",
    "TICKETS_PATH",
    "WorkerInput",
    "build_v8_nightly",
    "builder_for_server",
    "graph",
    "run_nightly",
    "schedule_local",
]

DATAFLOW = Path(__file__).resolve().parents[1]
TICKETS_PATH = DATAFLOW / "data" / "tickets.jsonl"
REPORTS_DIR = DATAFLOW / "data" / "reports"


class NightlyState(TypedDict, total=False):
    date: str
    tickets: list[dict]
    results: Annotated[list, operator.add]
    parked: Annotated[list, operator.add]
    report_path: str
    report: str
    load_mode: str


class WorkerInput(TypedDict):
    ticket: dict
    date: str


def _ticket_date(row: dict) -> str:
    created = str(row.get("created_at") or "")
    if "T" in created:
        return created.split("T", 1)[0]
    return created[:10]


def load_day_tickets(date: str, max_workers: int) -> dict[str, Any]:
    """Read tickets.jsonl. Match the date, or fall back to the whole file."""
    path = Path(TICKETS_PATH)
    rows: list[dict] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
    matched = [row for row in rows if _ticket_date(row) == date]
    if matched:
        return {
            "date": date,
            "tickets": matched,
            "load_mode": "date",
        }
    capped = rows[: int(max_workers)]
    return {
        "date": date,
        "tickets": capped,
        "load_mode": "fallback_whole_file",
    }


def _parked_from_result(result: Any, graph: Any, thread_id: str) -> bool:
    if isinstance(result, dict) and result.get("__interrupt__"):
        return True
    snap = graph.get_state({"configurable": {"thread_id": thread_id}})
    return bool(getattr(snap, "interrupts", None))


def write_report(state: NightlyState) -> dict[str, str]:
    date = str(state.get("date") or "")
    tickets = list(state.get("tickets") or [])
    results = list(state.get("results") or [])
    parked = list(state.get("parked") or [])
    skipped = [row for row in results if row.get("skipped")]
    answered = [row for row in results if not row.get("skipped")]
    lines = [
        "# Nightly triage " + date,
        "",
        "tickets: " + str(len(tickets)),
        "answered: " + str(len(answered)),
        "parked: " + str(len(parked)),
        "skipped: " + str(len(skipped)),
        "load_mode: " + str(state.get("load_mode") or ""),
        "",
        "Parked thread ids:",
    ]
    if parked:
        for row in parked:
            lines.append("- " + str(row.get("thread_id") or ""))
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("Answered:")
    if answered:
        for row in answered:
            lines.append(
                "- "
                + str(row.get("ticket_id") or "")
                + ": "
                + str(row.get("reply") or "")
            )
    else:
        lines.append("- (none)")
    if skipped:
        lines.append("")
        lines.append("Skipped:")
        for row in skipped:
            lines.append(
                "- "
                + str(row.get("ticket_id") or "")
                + " ("
                + str(row.get("reason") or "fan cap")
                + ")"
            )
    body = "\n".join(lines) + "\n"
    reports_dir = Path(REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / ("nightly-" + date + ".md")
    path.write_text(body, encoding="utf-8")
    return {"report_path": str(path), "report": body}


def build_v8_nightly(
    checkpointer=None,
    store=None,
    model=None,
    max_workers=20,
    *,
    for_server: bool = False,
):
    """Nightly fan of the v4 desk, capped, then a deferred report."""
    if not for_server and checkpointer is None:
        checkpointer = InMemorySaver()
    cap = int(max_workers)
    desk = build_v4_hitl(
        checkpointer=checkpointer,
        model=model,
        for_server=for_server,
    )

    def load_day(state: NightlyState) -> dict[str, Any]:
        date = str(state.get("date") or "")
        return load_day_tickets(date, cap)

    def fan(state: NightlyState) -> list[Send]:
        date = str(state.get("date") or "")
        tickets = list(state.get("tickets") or [])
        return [
            Send("worker", {"ticket": row, "date": date})
            for row in tickets[:cap]
        ]

    def mark_skipped(state: NightlyState) -> dict[str, list]:
        extra = list(state.get("tickets") or [])[cap:]
        if not extra:
            return {}
        return {
            "results": [
                {
                    "ticket_id": row.get("ticket_id"),
                    "skipped": True,
                    "reason": "fan cap",
                }
                for row in extra
            ]
        }

    def worker(state: WorkerInput) -> dict[str, list]:
        # v4 desk as a subgraph: own thread, same checkpointer, so a refund
        # parks on nightly-<date>-<ticket_id> and the inbox can list it.
        row = dict(state.get("ticket") or {})
        date = str(state.get("date") or "")
        ticket_id = str(row.get("ticket_id") or "")
        thread_id = "nightly-" + date + "-" + ticket_id
        result = desk.invoke(
            {"ticket": str(row.get("text") or "")},
            {"configurable": {"thread_id": thread_id}},
        )
        if _parked_from_result(result, desk, thread_id):
            return {
                "parked": [
                    {
                        "ticket_id": ticket_id,
                        "parked": True,
                        "thread_id": thread_id,
                    }
                ]
            }
        reply = None
        if isinstance(result, dict):
            reply = result.get("reply")
        return {
            "results": [
                {
                    "ticket_id": ticket_id,
                    "parked": False,
                    "thread_id": thread_id,
                    "reply": reply,
                }
            ]
        }

    builder = StateGraph(NightlyState)
    builder.add_node("load_day", load_day)
    builder.add_node("worker", worker, input_schema=WorkerInput)
    builder.add_node("mark_skipped", mark_skipped)
    builder.add_node("report", write_report, defer=True)
    builder.add_edge(START, "load_day")
    builder.add_conditional_edges("load_day", fan, ["worker"])
    builder.add_edge("load_day", "mark_skipped")
    builder.add_edge("mark_skipped", "report")
    builder.add_edge("worker", "report")
    builder.add_edge("report", END)
    kwargs: dict[str, Any] = {}
    if not for_server:
        kwargs["checkpointer"] = checkpointer
    if store is not None:
        kwargs["store"] = store
    return builder.compile(**kwargs)


def run_nightly(date: str, checkpointer, store=None, model=None, max_workers=20) -> dict:
    """Invoke the nightly graph on thread nightly-<date>."""
    compiled = build_v8_nightly(
        checkpointer=checkpointer,
        store=store,
        model=model,
        max_workers=max_workers,
    )
    thread_id = "nightly-" + date
    result = compiled.invoke(
        {"date": date},
        {"configurable": {"thread_id": thread_id}},
    )
    values = result if isinstance(result, dict) else {}
    return {
        "thread_id": thread_id,
        "report_path": values.get("report_path"),
        "report": values.get("report"),
        "tickets": values.get("tickets") or [],
        "results": values.get("results") or [],
        "parked": values.get("parked") or [],
        "load_mode": values.get("load_mode"),
    }


def schedule_local(hour: int, minute: int, run, run_now: bool = False):
    """Sleep until the next hour:minute, then call run.

    run_now=True skips the sleep and still prints when it would have fired.
    """
    now = datetime.now()
    target = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    print("would_fire_at", target.isoformat(sep=" ", timespec="seconds"))
    if run_now:
        print("run_now", True)
        return run()
    delay = (target - now).total_seconds()
    print("sleep_seconds", round(delay, 1))
    time.sleep(delay)
    return run()


def builder_for_server():
    """Compile without a checkpointer. The Agent Server injects persistence."""
    return build_v8_nightly(for_server=True)


graph = builder_for_server()
