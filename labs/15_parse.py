# %%
"""S15.2 Bad JSON retries once, then fail closed."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.tools.structured import parse_tool_json

# %%
good = parse_tool_json('{"found": true, "order_id": "DF-1001"}')
print("good_ok", good["ok"])

# %%
prefix = parse_tool_json('here you go {"found": false, "reason": "unknown order"}')
print("prefix_ok", prefix["ok"])

# %%
bad = parse_tool_json("not json at all")
print("bad_ok", bad["ok"])
print("fail_closed", bad.get("fail_closed"))
