# %% [markdown]
# Measure tokens before and after the death.
#
# Two counts from usage_metadata: the turn that stated the constraint,
# and the turn that needed it.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.rot import constraint_turn

side = root / "dataflow" / "context" / "_last_rot.json"
if not side.is_file():
    print("missing_rot_trace", str(side))
    print("run labs/03_02_context_rot.py first")
    raise SystemExit(0)

payload = json.loads(side.read_text(encoding="utf-8"))
trace = payload.get("trace") or []
fail_turn = payload.get("fail_turn")
before_row = None
after_row = None
for row in trace:
    if row.get("turn") == constraint_turn():
        before_row = row
    if fail_turn and row.get("turn") == fail_turn:
        after_row = row
if after_row is None and trace:
    after_row = trace[-1]

# %%
print("before_turn", None if before_row is None else before_row.get("turn"))
print("before_tokens", None if before_row is None else before_row.get("tokens"))
print("before_usage", None if before_row is None else before_row.get("usage"))
print("after_turn", None if after_row is None else after_row.get("turn"))
print("after_tokens", None if after_row is None else after_row.get("tokens"))
print("after_usage", None if after_row is None else after_row.get("usage"))
print("fail_turn", fail_turn)
if before_row and after_row:
    b = (before_row.get("usage") or {}).get("input_tokens")
    a = (after_row.get("usage") or {}).get("input_tokens")
    print("usage_input_before", b)
    print("usage_input_after", a)
    print(
        "meaning",
        "before is the constraint turn; after is the death or the last turn if the model did not fail",
    )
