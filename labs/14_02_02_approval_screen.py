# %% [markdown]
# Build the DataFlow refund approval screen.
#
# When this works, approve prints the write, reject prints the miss,
# edit prints the edited args. The planted reject still writes.

# %%
from pathlib import Path
import os
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from langgraph.checkpoint.memory import InMemorySaver

from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.refund import read_refunds
from dataflow.ui.desk_core import (
    approve,
    edit,
    reject,
    reject_planted,
    stream_tokens,
)
from dataflow.ui.page_server import run_page_shot

print("model", config.CHAT_MODEL)

handle = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
handle.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = handle.name
print("refunds_path", handle.name)

TICKET = "Please refund order DF-1001, the lamp is unused"
print("ticket", TICKET)

model = config.get_chat_model()
saver = InMemorySaver()
graph = build_v4_hitl(checkpointer=saver, model=model)


def park(thread_id: str):
    events = list(stream_tokens(graph, TICKET, thread_id))
    parks = [p for k, p in events if k == "interrupt"]
    print("parked", thread_id, bool(parks))
    if parks:
        print("payload", parks[0])
    return parks


# %%
print("cell", "approve_A")
park("thread-A")
done_a = approve(graph, "thread-A")
print("approve_reply", done_a.get("reply"))
print("approve_refund", done_a.get("refund"))
print("approve_rows", read_refunds())

# %%
print("cell", "reject_B")
park("thread-B")
rows_before = list(read_refunds())
done_b = reject(graph, "thread-B", "lamp was used")
print("reject_reply", done_b.get("reply"))
print("reject_miss", done_b.get("refund"))
print("reject_rows", read_refunds())
print("reject_wrote", len(read_refunds()) > len(rows_before))

# %%
print("cell", "edit_C")
park("thread-C")
done_c = edit(
    graph,
    "thread-C",
    {"amount": 20.0, "reason": "partial refund"},
)
print("edit_reply", done_c.get("reply"))
print("edit_refund", done_c.get("refund"))
print("edit_rows", read_refunds())

# %%
print("cell", "break_planted")
print("BREAK: reject_planted still writes")
park("thread-D")
rows_before_plant = list(read_refunds())
planted = reject_planted(graph, "thread-D", "should not write")
print("planted_reply", planted.get("reply"))
print("planted_refund", planted.get("refund"))
print("planted_rows", read_refunds())
print("planted_wrote", len(read_refunds()) > len(rows_before_plant))
print("FIX: reject resumes no, returns the typed miss, writes nothing")
print("committed_reject_miss", done_b.get("refund"))

# %%
print("cell", "streamlit_page")
screen_path = root / "dataflow" / "ui" / "screens" / "14_02_02.png"
committed = screen_path.read_bytes() if screen_path.is_file() else b""
try:
    shot = run_page_shot(
        "dataflow/ui/streamlit_desk.py",
        screen_path,
        extra_env={"DATAFLOW_UI_DEMO": "approval"},
        wait_text="Approve",
    )
    print("http_status", shot.get("status"))
    print("url", shot.get("url"))
    print("body_head", shot.get("body_head"))
    print("screenshot", shot.get("screenshot"))
finally:
    if committed:
        screen_path.write_bytes(committed)
        print("restored_screenshot", True)
    elif screen_path.is_file():
        print("screenshot_new", screen_path.as_posix())

# %% [markdown]
# restore: screenshot bytes were put back when they already lived in git
