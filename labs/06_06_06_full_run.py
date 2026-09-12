# %% [markdown]
# Watch a full DataFlow HITL run end to end on the stream.
#
# Lookup streams straight through. A refund parks. Approve resumes.
# Then pytest tests/test_dataflow_stream.py.

# %%
from pathlib import Path
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.types import Command

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.refund import get_refunds_path, read_refunds

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

lookup_ticket = by_id["T-3002"]
refund_ticket = by_id["T-3001"]
print("model", config.CHAT_MODEL)
print("lookup_ticket_id", lookup_ticket["ticket_id"])
print("lookup_text", lookup_ticket["text"])
print("refund_ticket_id", refund_ticket["ticket_id"])
print("refund_text", refund_ticket["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
print("refunds_path", refunds_path.as_posix())

graph = build_v4_hitl()
stream_kwargs = {
    "stream_mode": ["updates", "messages"],
    "version": "v2",
}


def print_diary(parts):
    reply = None
    message_chunks = 0
    for part in parts:
        kind = part.get("type") if isinstance(part, dict) else None
        data = part.get("data") if isinstance(part, dict) else part
        if kind == "updates":
            if not isinstance(data, dict):
                print("node", type(data).__name__, "keys", [])
                continue
            for node, update in data.items():
                if isinstance(update, dict):
                    keys = sorted(update.keys())
                    if "reply" in update:
                        reply = update.get("reply")
                else:
                    keys = [type(update).__name__]
                print("node", node, "keys", keys)
        elif kind == "messages":
            message_chunks += 1
    print("message_chunks", message_chunks)
    return reply


# %%
print("lookup")
lookup_cfg = {"configurable": {"thread_id": "lab-12-6-lookup"}}
lookup_reply = print_diary(
    graph.stream({"ticket": lookup_ticket["text"]}, lookup_cfg, **stream_kwargs)
)
lookup_state = graph.get_state(lookup_cfg)
print("lookup_reply", lookup_state.values.get("reply") or lookup_reply)
print("lookup_parked", bool(lookup_state.interrupts))

# %%
print("refund_park")
refund_cfg = {"configurable": {"thread_id": "lab-12-6-refund"}}
print_diary(
    graph.stream({"ticket": refund_ticket["text"]}, refund_cfg, **stream_kwargs)
)
parked = graph.get_state(refund_cfg)
print("refund_parked", bool(parked.interrupts))
if parked.interrupts:
    print("payload", parked.interrupts[0].value)
print("rows_before_resume", len(read_refunds()))

# %%
print("resume_approve")
# resume_with is graph.invoke(Command(resume=decision), config).
# Stream the same Command so the diary of the resume is visible.
resume_reply = print_diary(
    graph.stream(Command(resume="approve"), refund_cfg, **stream_kwargs)
)
done = graph.get_state(refund_cfg)
print("final_reply", done.values.get("reply") or resume_reply)
print("resume_parked", bool(done.interrupts))
rows = read_refunds()
print("refunds_rows", len(rows))
for row in rows:
    print("refund_row", row)

# %%
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_dataflow_stream.py", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", result.returncode)
