# %% [markdown]
# Queue two parked DataFlow runs into an inbox.
#
# When this works, two rows print with id, age and payload, then one
# approve and one reject by name. The planted resolve resumes the
# wrong thread. The fix is each row carries its own id.

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
    inbox_rows,
    reject,
    resolve_first,
    stream_tokens,
)
from dataflow.ui.page_server import run_page_shot

print("model", config.CHAT_MODEL)

handle = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
handle.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = handle.name
print("refunds_path", handle.name)

TICKET_A = "Please refund order DF-1001, the lamp is unused"
TICKET_B = "Order DF-1009 arrived damaged. I want a refund."

model = config.get_chat_model()
saver = InMemorySaver()
graph = build_v4_hitl(checkpointer=saver, model=model)

# %%
print("cell", "drop_two")
list(stream_tokens(graph, TICKET_A, "thread-A"))
list(stream_tokens(graph, TICKET_B, "thread-B"))
rows = inbox_rows(saver, graph)
print("inbox_rows", len(rows))
for row in rows:
    print("row_id", row.get("thread_id"))
    print("row_age_seconds", row.get("age_seconds"))
    print("row_payload", row.get("payload"))

# %%
print("cell", "resolve_by_name")
done_a = approve(graph, "thread-A")
print("named_approve_id", "thread-A")
print("named_approve_reply", done_a.get("reply"))
print("named_approve_refund", done_a.get("refund"))
done_b = reject(graph, "thread-B", "damaged item already replaced")
print("named_reject_id", "thread-B")
print("named_reject_reply", done_b.get("reply"))
print("named_reject_miss", done_b.get("refund"))
print("after_named_rows")
for row in inbox_rows(saver, graph):
    print("still_parked", row.get("thread_id"))
print("refunds_after_named", read_refunds())

# %%
print("cell", "break_resolve_first")
print("BREAK: the planted resolve resumes the wrong thread")
list(stream_tokens(graph, TICKET_A, "thread-E"))
list(stream_tokens(graph, TICKET_B, "thread-F"))
before = inbox_rows(saver, graph)
print("parked_before_plant")
for row in before:
    print("parked", row.get("thread_id"))
intended = "thread-F"
print("reviewer_intended", intended)
planted = resolve_first(graph, saver, "approve")
print("planted_moved", planted.get("thread_id"))
print("planted_equals_intended", planted.get("thread_id") == intended)
print("planted_reply", planted.get("reply"))
print("planted_refund", planted.get("refund"))
print("FIX: each row carries its own id")
list(stream_tokens(graph, TICKET_A, "thread-G"))
list(stream_tokens(graph, TICKET_B, "thread-H"))
fix_a = approve(graph, "thread-G")
fix_b = reject(graph, "thread-H", "not this order")
print("fix_approve_id", "thread-G")
print("fix_approve_outcome", fix_a.get("refund") or fix_a.get("reply"))
print("fix_reject_id", "thread-H")
print("fix_reject_outcome", fix_b.get("refund") or fix_b.get("reply"))

# %%
print("cell", "streamlit_page")
screen_path = root / "dataflow" / "ui" / "screens" / "14_02_04.png"
committed = screen_path.read_bytes() if screen_path.is_file() else b""
try:
    shot = run_page_shot(
        "dataflow/ui/inbox.py",
        screen_path,
        extra_env={"DATAFLOW_UI_DEMO": "inbox"},
        wait_text="night-T-3001",
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
