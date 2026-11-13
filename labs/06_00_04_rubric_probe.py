# %%
"""Lab 9.4: hold the rubric against the finished DataFlow desk.

What we build: nothing new. You run four of the five rubric probes against the DataFlow graph desk that
this part ends with (build_v4_hitl): park, survive a kill, test one decision, see every step. Each probe
prints PASS or FAIL and the one line of evidence it rests on. The fifth probe, change it while runs are in
flight, is Section 18's job, and the last line says so. You do not need to read this code yet; each probe
names the section that teaches it.

What you learn: a rubric question is answered by a run, not a slide. Park: the refund ticket stops before
any money moves (Section 14). Survive a kill: one process parks the refund and dies; a second process, a
fresh start, finds the parked refund in the SQLite file and finishes it (Section 13). Test one decision:
the routing rule is a plain function you call with no model and no graph (Section 11). See every step: the
run reports one update per node (Section 15).

What will be true on your screen: the model line and the versions, then each probe's PROBE line and its
evidence line. The refunds ledger is a file in a temporary folder for this run, so the repo's own
dataflow/data/refunds.jsonl is never written.
"""

from importlib.metadata import version
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

import config
from dataflow.graphs.v4_hitl import build_v4_hitl, pick_route
from dataflow.tools.refund import read_refunds

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
REFUND_TICKET = by_id["T-3001"]["text"]
LOOKUP_TICKET = by_id["T-3002"]["text"]
KILL_THREAD = {"configurable": {"thread_id": "rubric-kill"}}

# %%
# The two child processes of the survive-a-kill probe run this file again with one of these two words.
if len(sys.argv) == 3 and sys.argv[1] in ("--park-and-die", "--resume"):
    with SqliteSaver.from_conn_string(sys.argv[2]) as saver:
        desk = build_v4_hitl(checkpointer=saver, model=config.get_chat_model())
        if sys.argv[1] == "--park-and-die":
            out = desk.invoke({"ticket": REFUND_TICKET}, KILL_THREAD)
            print(json.dumps({"pid": os.getpid(), "parked": bool(out.get("__interrupt__")), "next": list(desk.get_state(KILL_THREAD).next)}), flush=True)
            os._exit(0)  # die on the spot: no clean shutdown, as if the process were killed
        parked = desk.get_state(KILL_THREAD)
        payload = parked.interrupts[0].value if parked.interrupts else None
        out = desk.invoke(Command(resume={"action": "approve", "actor": "rubric-reviewer"}), KILL_THREAD)
        print(json.dumps({"pid": os.getpid(), "next": list(parked.next), "payload": payload, "reply": out.get("reply")}), flush=True)
    sys.exit(0)

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

# The refunds ledger for this run only: a temp file, as the HITL tests do. The child processes inherit it.
work = Path(tempfile.mkdtemp(prefix="rubric_probe_"))
os.environ["DATAFLOW_REFUNDS_PATH"] = str(work / "refunds.jsonl")


def verdict(name: str, ok: bool, evidence: str) -> None:
    print("PROBE", name, "PASS" if ok else "FAIL")
    print("evidence", evidence)


# %%
# Probe 1, park (Section 14): the refund ticket stops before the write.
desk = build_v4_hitl(model=chat)
park = {"configurable": {"thread_id": "rubric-park"}}
out = desk.invoke({"ticket": REFUND_TICKET}, park)
waiting = desk.get_state(park).next
question = out["__interrupt__"][0].value["question"] if out.get("__interrupt__") else None
rows = len(read_refunds())
verdict("park", bool(question) and waiting == ("refund",) and rows == 0,
        f"route {out.get('route')}, next {waiting}, the reviewer is asked: {question} refunds.jsonl rows {rows}")

# %%
# Probe 2, survive a kill (Section 13): one process parks and dies; a second one resumes from the SQLite file.
db = str(work / "rubric.sqlite")
me = Path(__file__).resolve()
first = subprocess.run([sys.executable, str(me), "--park-and-die", db], capture_output=True, text=True, encoding="utf-8", cwd=root)
second = subprocess.run([sys.executable, str(me), "--resume", db], capture_output=True, text=True, encoding="utf-8", cwd=root)
try:
    a = json.loads(first.stdout.strip().splitlines()[-1])
    b = json.loads(second.stdout.strip().splitlines()[-1])
except (IndexError, json.JSONDecodeError):
    print("child stderr", (first.stderr + second.stderr)[-1500:])
    a, b = {}, {}
payload = b.get("payload") or {}
print("parked payload", json.dumps(payload))
rows = len(read_refunds())
verdict("survive_kill",
        a.get("parked") is True and a.get("pid") != b.get("pid") and payload.get("order_id") == "DF-1001"
        and str(b.get("reply", "")).startswith("Refund issued") and rows == 1,
        f"process {a.get('pid')} parked at {a.get('next')} and died; process {b.get('pid')} found it waiting at "
        f"{b.get('next')}, resumed with approve: {b.get('reply')} refunds.jsonl rows {rows}")

# %%
# Probe 3, test one decision (Section 11): the routing rule alone, no model, no graph.
labels = ("refund", "lookup", "policy", "billing", "")
decisions = {label: pick_route({"route": label}) for label in labels}
verdict("test_one_decision",
        decisions == {"refund": "refund", "lookup": "lookup", "policy": "policy", "billing": "lookup", "": "lookup"},
        f"pick_route alone: {decisions}")

# %%
# Probe 4, see every step (Section 15): one update per node that ran.
steps = []
for update in desk.stream({"ticket": LOOKUP_TICKET}, {"configurable": {"thread_id": "rubric-steps"}}, stream_mode="updates"):
    for node, values in update.items():
        steps.append(node)
        print("step", node, json.dumps(values, default=str)[:160])
verdict("see_every_step", steps[:1] == ["classify"] and len(steps) >= 2, "nodes in order: " + " -> ".join(steps))

# %%
print("PROBE change_it NOT RUN HERE: Section 18, change a graph while threads are live")
