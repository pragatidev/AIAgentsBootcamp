# %% [markdown]
# Pass an actor id through runtime context.
#
# When this works, a refund approve with user_id reviewer-1 prints
# actor=reviewer-1 on the trace. The break logs admin when the id is
# missing. The test fails unless the logged actor equals the invoking user.

# %%
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.v1_triage import DeskContext
from dataflow.ops import tracer
from dataflow.tools.refund import (
    actor_from_runtime_admin,
    build_confirm_graph,
    resume_confirm,
)

print("model", config.CHAT_MODEL)
handle = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
handle.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = handle.name

# %%
print("cell", "approve_with_user_id")
os.environ.pop("DATAFLOW_ACTOR_ADMIN_FALLBACK", None)
graph = build_confirm_graph()
cfg = {"configurable": {"thread_id": "actor-ok"}}
ctx = DeskContext(user_id="reviewer-1")
graph.invoke(
    {
        "order_id": "DF-1001",
        "amount": 89.0,
        "reason": "unused lamp",
        "actor": "",
    },
    cfg,
    context=ctx,
)
resume_confirm(graph, cfg, {"action": "approve"})
print("trace_line", tracer.last_actor_line)

# %%
print("cell", "break_admin_fallback")
print("admin_variant", actor_from_runtime_admin())
env = os.environ.copy()
env["DATAFLOW_ACTOR_ADMIN_FALLBACK"] = "1"
red = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_guardrails_actor.py::test_logged_actor_equals_invoking_user",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    env=env,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(red.stdout)
print("red_exit", red.returncode)

green_env = os.environ.copy()
green_env.pop("DATAFLOW_ACTOR_ADMIN_FALLBACK", None)
green = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_guardrails_actor.py::test_logged_actor_equals_invoking_user",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    env=green_env,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(green.stdout)
print("green_exit", green.returncode)
