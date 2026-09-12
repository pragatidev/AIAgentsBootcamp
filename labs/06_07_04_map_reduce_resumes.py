# %% [markdown]
# Map-reduce over the TalentFlow resume pile.
#
# load reads the job and the resumes. fan_out returns one Send per
# resume. All score copies share one superstep. summarize ranks them.
# Ollama runs the copies one at a time locally.

# %%
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from talentflow.graphs.score_resumes import (
    build_score_resumes,
    fan_out,
    load_resumes,
)

print("model", config.CHAT_MODEL)

loaded = load_resumes()
sends = fan_out(loaded)
print("resumes_loaded", len(loaded["resumes"]))
print("sends", len(sends))

graph = build_score_resumes()
thread = {"configurable": {"thread_id": "lab-13-4"}}
started = time.perf_counter()
out = graph.invoke({}, thread)
elapsed = time.perf_counter() - started
print("elapsed_seconds", round(elapsed, 2))

rows = list(out.get("scores") or [])
rows = sorted(rows, key=lambda r: (-int(r.get("score") or 0), str(r.get("name") or "")))
print("ranking_table")
print("name\tscore\tfit")
for row in rows:
    print(str(row.get("name")), str(row.get("score")), str(row.get("fit")))
print("summary")
print(out.get("ranking"))
print(
    "ollama_note",
    "Ollama runs the score copies one at a time locally, so the wall clock gain shows on a hosted provider",
)


def write_nodes(snap) -> list:
    meta = snap.metadata or {}
    writes = meta.get("writes", {})
    if isinstance(writes, dict):
        return [name for name in writes if not str(name).startswith("__")]
    if writes:
        return list(writes)
    return []


history = list(reversed(list(graph.get_state_history(thread))))
print("history_oldest_first", len(history))
for snap in history:
    meta = snap.metadata or {}
    step = meta.get("step")
    nodes = write_nodes(snap)
    task_names = [t.name for t in (snap.tasks or ())]
    print(
        "step",
        step,
        "writes",
        nodes,
        "next",
        list(snap.next or ()),
        "tasks",
        task_names,
    )

# %%
print("limit_3")
loaded_three = load_resumes(limit=3)
sends_three = fan_out(loaded_three)
print("resumes_loaded", len(loaded_three["resumes"]))
print("sends", len(sends_three))
short = build_score_resumes(limit=3)
thread_short = {"configurable": {"thread_id": "lab-13-4-short"}}
started_short = time.perf_counter()
out_short = short.invoke({}, thread_short)
elapsed_short = time.perf_counter() - started_short
print("elapsed_seconds", round(elapsed_short, 2))
rows_short = list(out_short.get("scores") or [])
rows_short = sorted(
    rows_short,
    key=lambda r: (-int(r.get("score") or 0), str(r.get("name") or "")),
)
print("ranking_table")
print("name\tscore\tfit")
for row in rows_short:
    print(str(row.get("name")), str(row.get("score")), str(row.get("fit")))
print("summary")
print(out_short.get("ranking"))
