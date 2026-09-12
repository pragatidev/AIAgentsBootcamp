"""Tiny trigger: a file lands, invoke the desk. Dumb by design."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

DATAFLOW = Path(__file__).resolve().parents[1]
AMBIENT_DB = DATAFLOW / "data" / "ambient.sqlite"


def on_new_ticket(path: Path, graph, checkpointer=None) -> dict:
    """Turn a file arriving into an invoke on a new thread.

    The trigger is tiny and dumb by design. The desk thinks; this file does not.
    Thread id comes from the ticket id so a reviewer can find the run.
    """
    del checkpointer
    row = json.loads(Path(path).read_text(encoding="utf-8"))
    thread_id = str(row.get("ticket_id") or Path(path).stem)
    text = str(row.get("text") or "")
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"ticket": text}, config)
    snap = graph.get_state(config)
    parked = bool(getattr(snap, "interrupts", None))
    reply = None
    if isinstance(result, dict):
        reply = result.get("reply")
    out = {"thread_id": thread_id, "parked": parked, "reply": reply}
    if parked:
        out["payload"] = snap.interrupts[0].value
    return out


def watch(folder: Path, graph, once: bool = False, poll_seconds: float = 1.0):
    """Poll a folder for new .json files. Plain os.listdir, no third party watcher."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    results: list[dict] = []
    while True:
        for name in os.listdir(folder):
            if not name.endswith(".json") or name in seen:
                continue
            seen.add(name)
            results.append(on_new_ticket(folder / name, graph))
        if once:
            return results
        time.sleep(poll_seconds)
