# %% [markdown]
# Load-test the DataFlow desk.
#
# When this works, the replay prints tickets per minute, p95 latency,
# tokens per ticket and a spend column derived from tokens. Then the
# break: no timeout, a slow node, the suite stalls and is killed. Put
# the timeout back and the slow ticket is marked HUNG while the others
# finish.

# %%
from pathlib import Path
import sys
import threading

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from eval.load.replay import print_table, run_replay
from eval.runners.golden import load_golden

print("model", config.CHAT_MODEL)
print("cell", "run_replay")
report = run_replay(concurrency=4, timeout=60.0)
print_table(report)

# %%
print("cell", "break_no_timeout")
# Planted miss: no per-ticket timeout, one slow node. The lab itself
# cannot hang forever, so a background thread is joined with a hard cap.
HARD_CAP = 8
box = {"done": False}

def _stall() -> None:
    run_replay(
        rows=load_golden()[:2],
        concurrency=2,
        timeout=None,
        slow_node=True,
        slow_seconds=30.0,
        progress=True,
    )
    box["done"] = True

worker = threading.Thread(target=_stall, daemon=True)
worker.start()
worker.join(HARD_CAP)
if worker.is_alive():
    print("the suite stalled past", HARD_CAP, "seconds and was killed")
else:
    print("stall_thread_finished", box["done"])

# %%
print("cell", "timeout_back_hung_marked")
hung = run_replay(
    concurrency=4,
    timeout=45.0,
    slow_node=True,
    slow_seconds=90.0,
)
print_table(hung)
print("hung_count", sum(1 for row in hung["rows"] if row.get("status") == "HUNG"))
