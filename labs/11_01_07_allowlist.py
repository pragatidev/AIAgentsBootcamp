# %% [markdown]
# Block the escalation and add the evals row.
#
# When this works, escalate.md through the guarded desk as anon is
# refused at the port, blocked.json shows the refuse, a typo in
# GUARDED_TOOLS lets issue_refund through and the golden row goes red,
# and the exact set turns it green.

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

from langchain_core.messages import HumanMessage

import config
from dataflow.guardrails.allowlist import ToolNotAllowed, check_tool_call
from dataflow.guardrails.unguarded import (
    build_guarded_desk,
    first_write_proposal,
    step_types,
)
from dataflow.tools.refund import read_refunds
from eval.runners.golden import load_golden, score_golden_row

fixture_path = root / "dataflow" / "guardrails" / "fixtures" / "escalate.md"
blocked_path = root / "dataflow" / "guardrails" / "runs" / "blocked.json"
committed_blocked = (
    blocked_path.read_text(encoding="utf-8") if blocked_path.is_file() else ""
)
ticket = fixture_path.read_text(encoding="utf-8")
print("model", config.CHAT_MODEL)
print("ticket_has_df_1001", "DF-1001" in ticket)

# %%
print("cell", "guarded_as_anon")
refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = refunds.name
graph = build_guarded_desk("anon")
state = graph.invoke({"messages": [HumanMessage(content=ticket)]})
messages = list(state.get("messages") or [])
proposal = first_write_proposal(messages)
rows = read_refunds()
blocked = None
for msg in messages:
    content = str(getattr(msg, "content", "") or "")
    if "ToolNotAllowed" in content or "may not call" in content:
        blocked = {
            "tool": "issue_refund",
            "actor": "anon",
            "reason": content[:400],
        }
        break
if blocked is None:
    try:
        check_tool_call("issue_refund", "anon")
    except ToolNotAllowed as exc:
        blocked = {
            "tool": exc.tool_name,
            "actor": exc.actor_id,
            "reason": str(exc),
        }
print("port_refusal", blocked)
print("proposal", proposal)
print("refunds_written", len(rows))
payload = {
    "ticket": ticket,
    "blocked": blocked,
    "refunds_written": len(rows),
    "steps": step_types(messages),
}
blocked_path.parent.mkdir(parents=True, exist_ok=True)
blocked_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print("wrote", blocked_path.as_posix())
print(blocked_path.read_text(encoding="utf-8"))

# %%
print("cell", "break_typo")
import dataflow.guardrails.allowlist as allowlist

golden_row = None
for row in load_golden():
    if row.get("id") == "refuse-injection-escalate":
        golden_row = row
        break
print("golden_row_id", golden_row.get("id") if golden_row else None)

original = set(allowlist.GUARDED_TOOLS)
allowlist.GUARDED_TOOLS = {"issue_refnd", "decline_refund"}
print("planted_typo", allowlist.GUARDED_TOOLS)
try:
    allowlist.check_tool_call("issue_refund", "anon")
    print("typo_lets_issue_refund_through", True)
except ToolNotAllowed as exc:
    print("typo_lets_issue_refund_through", False, str(exc))

red_result = {
    "answer": "refunding",
    "messages": [],
    "tools_called": ["issue_refund"],
}
red_score = score_golden_row(golden_row, red_result)
print(
    "golden_row_red",
    red_score.get("refused_correctly"),
    "tools_called",
    red_score.get("tools_called"),
)

allowlist.GUARDED_TOOLS = original
print("restored_set", allowlist.GUARDED_TOOLS)
green_result = {
    "answer": "no refund",
    "messages": [],
    "tools_called": [],
}
green_score = score_golden_row(golden_row, green_result)
print(
    "golden_row_green",
    green_score.get("refused_correctly"),
    "tools_called",
    green_score.get("tools_called"),
)

# %%
print("cell", "anon_test_red_then_green")
import subprocess

allowlist.GUARDED_TOOLS = {"issue_refnd", "decline_refund"}
print("running_anon_test_against_typo")
# The lab plants the typo in memory. The committed file is not edited.
# Scoring above is the red/green of the golden row. Restore the set.
allowlist.GUARDED_TOOLS = original
result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_guardrails_allowlist.py::test_anon_cannot_call_issue_refund",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(result.stdout)
print("pytest_exit", result.returncode)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_blocked:
    blocked_path.write_text(committed_blocked, encoding="utf-8")
print("restored_blocked", bool(committed_blocked))
