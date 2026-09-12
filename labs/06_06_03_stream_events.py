# %% [markdown]
# stream_events v3 on the HITL desk: a refund parks, then approve resumes.
#
# Iterate the typed projections, print interrupted and the interrupt
# payload, then resume with Command and print the final output.

# %%
from pathlib import Path
import json
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

ticket = by_id["T-3001"]
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
print("refunds_path", refunds_path.as_posix())

graph = build_v4_hitl()
thread = {"configurable": {"thread_id": "lab-12-3"}}

# %%
stream = graph.stream_events({"ticket": ticket["text"]}, thread, version="v3")
print("dir_stream", dir(stream))
print(
    "stream_attrs",
    [name for name in dir(stream) if not name.startswith("_")],
)

if hasattr(stream, "values"):
    print("iterating values")
    for i, val in enumerate(stream.values):
        keys = sorted(val.keys()) if isinstance(val, dict) else type(val).__name__
        print("value_step", i, keys)
elif hasattr(stream, "messages"):
    print("iterating messages")
    for i, handle in enumerate(stream.messages):
        print("message_handle", i, type(handle).__name__)
else:
    print("iterating raw stream")
    for i, event in enumerate(stream):
        print("event", i, event)

interrupted = getattr(stream, "interrupted", None)
print("interrupted", interrupted)
interrupts = getattr(stream, "interrupts", None)
print("interrupts", interrupts)
if interrupts:
    for item in interrupts:
        value = item.value if hasattr(item, "value") else item
        print("interrupt_value", value)

# %%
resume_stream = graph.stream_events(
    Command(resume="approve"),
    thread,
    version="v3",
)
print("resume_dir_stream", dir(resume_stream))
print(
    "resume_stream_attrs",
    [name for name in dir(resume_stream) if not name.startswith("_")],
)
output = getattr(resume_stream, "output", None)
print("output", output)
rows = read_refunds()
print("refunds_rows", len(rows))
for row in rows:
    print("refund_row", row)
print("refund_exists", len(rows) > 0)
