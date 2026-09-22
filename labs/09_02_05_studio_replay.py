# %% [markdown]
# Replay a DataFlow run in LangSmith Studio.
#
# No checkpointer, so get_state_history is empty. Add InMemorySaver,
# edit the retrieved chunk, rerun. The second answer cites the edited
# chunk in this terminal. Then do the same edit with a mouse in Studio: run
# `langgraph dev`, pick the replay graph, and run the ticket there to get a
# thread on the server. The terminal thread below never leaves this process.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from src.paths import load_dotenv

load_dotenv(root)

import config
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.tools.retrieve import get_index
from langgraph.checkpoint.memory import InMemorySaver

TICKET = "Can I get a ninety-day refund on an unused lamp?"
THREAD_ID = "lab-27-5"
EDITED_CHUNK = (
    "EDITED CHUNK: the packing slip window is fourteen days. "
    "Cite the packing slip window in the answer."
)
STUDIO_URL = "https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024"
SERVER_URL = "http://127.0.0.1:2024"

print("model", config.CHAT_MODEL)
print("ticket", TICKET)
print("thread_id", THREAD_ID)
print("building_index", flush=True)
get_index(scope="all")
print("index_ready", flush=True)

# %%
print("cell", "no_checkpointer", flush=True)
graph = build_rag_graph(scope="all", grade_enabled=False, cite_node=None, checkpointer=None)
out = graph.invoke({"question": TICKET})
print("reply_no_saver", out.get("reply") if isinstance(out, dict) else out, flush=True)
cfg = {"configurable": {"thread_id": THREAD_ID}}
history = []
try:
    history = list(graph.get_state_history(cfg))
except Exception as exc:
    print("history_error", type(exc).__name__, exc, flush=True)
    history = []
print("history_len", len(history), flush=True)

# %%
print("cell", "with_saver", flush=True)
saver = InMemorySaver()
graph2 = build_rag_graph(scope="all", grade_enabled=False, cite_node=None, checkpointer=saver)
out2 = graph2.invoke({"question": TICKET}, cfg)
print("reply_with_saver", out2.get("reply") if isinstance(out2, dict) else out2, flush=True)
history2 = list(graph2.get_state_history(cfg))
print("checkpoint_count", len(history2), flush=True)
state = graph2.get_state(cfg)
values = state.values or {}
passages = list(values.get("passages") or [])
graded = list(values.get("graded") or [])
chunk = {}
if graded:
    chunk = dict(graded[0])
elif passages:
    chunk = dict(passages[0])
print("retrieved_chunk_source", chunk.get("source"), flush=True)
print("retrieved_chunk_text", chunk.get("text"), flush=True)

# %%
print("cell", "edit_and_replay", flush=True)
edited = dict(chunk)
edited["text"] = EDITED_CHUNK
if not edited.get("source"):
    edited["source"] = "edited-chunk"
graph2.update_state(
    cfg,
    {"passages": [edited], "graded": [edited]},
    as_node="retrieve",
)
out3 = graph2.invoke(None, cfg)
answer2 = str(
    (out3.get("answer") if isinstance(out3, dict) else None)
    or (out3.get("reply") if isinstance(out3, dict) else None)
    or out3
    or ""
)
print("second_answer", answer2, flush=True)
lower = answer2.lower()
cites = (
    "fourteen" in lower
    or "packing slip" in lower
    or "edited chunk" in lower
)
print("cites_edited_chunk", cites, flush=True)

# %%
print("cell", "studio", flush=True)
print("langgraph_dev_command", "langgraph dev", flush=True)
print("server_url", SERVER_URL, flush=True)
print("studio_url", STUDIO_URL, flush=True)
print("thread_id", THREAD_ID, flush=True)
print(
    "studio_note",
    "Open Studio on port 2024 and pick the replay graph, the one this lab just ran. "
    "The thread above lives in this process only, so run the same ticket in Studio to "
    "make a thread on the server, then edit the retrieved chunk in its state and resume.",
    flush=True,
)
