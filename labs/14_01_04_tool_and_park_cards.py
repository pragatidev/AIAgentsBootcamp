# %% [markdown]
# Render tool calls and interrupts as cards.
#
# When this works, a refund ticket prints a tool card and a park card.
# Raw JSON makes the park look like a crash. The card names the tool
# and the waiting state.

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
from dataflow.ui.desk_core import events_as_json, stream_tokens
from dataflow.ui.page_server import run_page_shot

print("model", config.CHAT_MODEL)

handle = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
handle.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = handle.name
print("refunds_path", handle.name)

TICKET = "Please refund order DF-1001, the lamp is unused"
print("ticket", TICKET)

graph = build_v4_hitl(
    checkpointer=InMemorySaver(),
    model=config.get_chat_model(),
)

# %%
print("cell", "cards")
events = list(stream_tokens(graph, TICKET, "lab-14-1-4"))
tool_cards = [p for k, p in events if k == "tool_call"]
park_cards = [p for k, p in events if k == "interrupt"]
nodes = [p for k, p in events if k == "node"]
print("nodes", nodes)
print("tool_card_count", len(tool_cards))
for card in tool_cards:
    print("tool_card_name", card.get("name") if isinstance(card, dict) else card)
    print("tool_card_args", card.get("args") if isinstance(card, dict) else None)
print("park_card_count", len(park_cards))
for park in park_cards:
    if isinstance(park, dict):
        print("park_card_action", park.get("action"))
        print("park_card_order_id", park.get("order_id"))
        print("park_card_amount", park.get("amount"))
        print("park_card_question", park.get("question"))
        print("park_card_fields", sorted(park.keys()))
    else:
        print("park_card", park)

# %%
print("cell", "break_raw")
print("BREAK: the UI prints raw JSON and the park looks like a crash")
print(events_as_json(events))
print("the park looks like a crash")

# %%
print("cell", "fix")
print("FIX: the card names the tool and the waiting state")
if tool_cards:
    card = tool_cards[0]
    print("fix_tool_name", card.get("name") if isinstance(card, dict) else card)
if park_cards:
    park = park_cards[0]
    waiting = None
    if isinstance(park, dict):
        waiting = park.get("action") or "refund"
    print("fix_waiting_state", waiting)

# %%
print("cell", "streamlit_page")
screen_path = root / "dataflow" / "ui" / "screens" / "14_01_04.png"
committed = screen_path.read_bytes() if screen_path.is_file() else b""
try:
    shot = run_page_shot(
        "dataflow/ui/streamlit_desk.py",
        screen_path,
        extra_env={"DATAFLOW_UI_DEMO": "cards"},
        wait_text="Tool:",
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
