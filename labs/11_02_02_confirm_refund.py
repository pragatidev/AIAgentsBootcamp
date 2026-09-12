# %% [markdown]
# Confirm-before-write on the DataFlow refund tool.
#
# When this works, the refund parks, deny writes nothing, approve writes
# one row, and a copy with the write above interrupt double-charges.

# %%
from pathlib import Path
import json
import os
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.tools.refund import (
    build_confirm_graph,
    get_refunds_path,
    read_refunds,
    resume_confirm,
)

print("model", config.CHAT_MODEL)
run_path = root / "dataflow" / "guardrails" / "runs" / "confirm.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""

payload_in = {
    "order_id": "DF-1001",
    "amount": 89.0,
    "reason": "unused lamp",
    "actor": "reviewer-1",
}

def temp_refunds() -> str:
    handle = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
    handle.close()
    os.environ["DATAFLOW_REFUNDS_PATH"] = handle.name
    return handle.name

# %%
print("cell", "park_then_deny")
deny_path = temp_refunds()
graph = build_confirm_graph()
deny_cfg = {"configurable": {"thread_id": "confirm-deny"}}
graph.invoke(dict(payload_in), deny_cfg)
state = graph.get_state(deny_cfg)
print("parked", bool(state.interrupts))
print("payload", state.interrupts[0].value if state.interrupts else None)
resume_confirm(graph, deny_cfg, {"action": "deny"})
deny_rows = read_refunds()
print("deny_rows", deny_rows)
print("deny_count", len(deny_rows))

# %%
print("cell", "fresh_thread_approve")
approve_path = temp_refunds()
graph2 = build_confirm_graph()
ok_cfg = {"configurable": {"thread_id": "confirm-approve"}}
graph2.invoke(dict(payload_in), ok_cfg)
resume_confirm(graph2, ok_cfg, {"action": "approve"})
ok_rows = read_refunds()
print("approve_rows", ok_rows)
print("approve_count", len(ok_rows))

outcomes = {
    "deny": {"rows": deny_rows, "count": len(deny_rows), "path": deny_path},
    "approve": {"rows": ok_rows, "count": len(ok_rows), "path": approve_path},
}
run_path.parent.mkdir(parents=True, exist_ok=True)
run_path.write_text(json.dumps(outcomes, indent=2) + "\n", encoding="utf-8")
print("wrote", run_path.as_posix())
print(run_path.read_text(encoding="utf-8"))

# %%
print("cell", "break_write_before_interrupt")
plant_path = temp_refunds()
planted = build_confirm_graph(write_before_interrupt=True)
plant_cfg = {"configurable": {"thread_id": "planted"}}
planted.invoke(dict(payload_in), plant_cfg)
print("rows_after_park", len(read_refunds()))
resume_confirm(planted, plant_cfg, {"action": "approve"})
print("rows_after_resume", len(read_refunds()))
print("double_charge", len(read_refunds()) == 2)
print("fix_is_committed_order", "write sits after interrupt")

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_run:
    run_path.write_text(committed_run, encoding="utf-8")
print("restored_confirm", bool(committed_run))
print("refunds_path_now", str(get_refunds_path()))
