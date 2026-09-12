# %% [markdown]
# Fork a checkpoint before speak and continue with an edited finding.
#
# The original trail stays intact. Speak runs again on the fork.
# get_state on the plain thread config is the fork tip after the fork.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.v3_memory import build_v3_memory

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

graph = build_v3_memory()
config_thread = {"configurable": {"thread_id": "lab-12-5"}}

# %%
first = graph.invoke({"ticket": ticket["text"]}, config_thread)
original_reply = first.get("reply")
print("original_reply", original_reply)

history_before = list(graph.get_state_history(config_thread))
print("history_before", len(history_before))
print("history newest first")
before_speak = None
for snap in history_before:
    meta = snap.metadata or {}
    step = meta.get("step")
    checkpoint_id = snap.config["configurable"]["checkpoint_id"]
    print("step", step, "next", snap.next, "checkpoint_id", checkpoint_id)
    if tuple(snap.next) == ("speak",) and before_speak is None:
        before_speak = snap

if before_speak is None:
    raise SystemExit("no checkpoint with next=('speak',)")

print("fork_from_next", before_speak.next)
print(
    "fork_from_checkpoint_id",
    before_speak.config["configurable"]["checkpoint_id"],
)

edited = "The return window is 30 days and the lamp qualifies."
fork_config = graph.update_state(
    before_speak.config,
    values={"reply": edited},
)
forked = graph.invoke(None, fork_config)
fork_reply = forked.get("reply")
print("fork_reply", fork_reply)

# %%
newest = graph.get_state(config_thread)
print("newest_is_fork_tip True")
print("newest_reply", newest.values.get("reply"))
print(
    "newest_matches_fork_reply",
    newest.values.get("reply") == fork_reply,
)
history_after = list(graph.get_state_history(config_thread))
print("history_before", len(history_before))
print("history_after", len(history_after))
print("history_grew", len(history_after) > len(history_before))
print("original_reply", original_reply)
print("fork_reply", fork_reply)
