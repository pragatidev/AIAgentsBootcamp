# %% [markdown]
# Stream the DataFlow desk into Streamlit.
#
# When this works, tokens print as they arrive, then the node rows.
# invoke prints nothing for the whole wait and then everything.

# %%
from pathlib import Path
import os
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from langgraph.checkpoint.memory import InMemorySaver

from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.ui.desk_core import run_blocking, stream_tokens
from dataflow.ui.page_server import run_page_shot

print("model", config.CHAT_MODEL)
print("python", sys.executable)

handle = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
handle.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = handle.name
print("refunds_path", handle.name)

TICKET = "Where is order DF-1002?"
print("ticket", TICKET)

graph = build_v4_hitl(
    checkpointer=InMemorySaver(),
    model=config.get_chat_model(),
)

# %%
print("cell", "stream_tokens")
line = ""
nodes = []
t0 = time.perf_counter()
first_s = None
for kind, payload in stream_tokens(graph, TICKET, "lab-14-1-3-stream"):
    if first_s is None:
        first_s = time.perf_counter() - t0
        print("stream_first_byte_s", round(first_s, 3))
    if kind == "token":
        line += str(payload)
        print("\r" + line, end="", flush=True)
    elif kind == "node":
        nodes.append(str(payload))
print()
print("stream_line", line)
print("stream_nodes", nodes)

# %%
print("cell", "break_blocking")
print("BREAK: invoke blocks. Nothing prints until the graph is done.")
block_graph = build_v4_hitl(
    checkpointer=InMemorySaver(),
    model=config.get_chat_model(),
)
t1 = time.perf_counter()
block_first = None
block_events = []
for kind, payload in run_blocking(block_graph, TICKET, "lab-14-1-3-block"):
    if block_first is None:
        block_first = time.perf_counter() - t1
        print("blocking_first_byte_s", round(block_first, 3))
    block_events.append((kind, payload))
print("blocking_event_count", len(block_events))
print("blocking_events")
for kind, payload in block_events:
    print(kind, payload)
print("FIX: stream_tokens yields as the run happens. invoke waits, then dumps.")

# %%
print("cell", "streamlit_page")
screen_path = root / "dataflow" / "ui" / "screens" / "14_01_03.png"
committed = screen_path.read_bytes() if screen_path.is_file() else b""
try:
    shot = run_page_shot(
        "dataflow/ui/streamlit_desk.py",
        screen_path,
        extra_env={"DATAFLOW_UI_DEMO": ""},
        wait_text="DataFlow desk",
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
