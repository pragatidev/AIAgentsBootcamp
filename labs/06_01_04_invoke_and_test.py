# %% [markdown]
# Compile, invoke, and unit-test one node.
#
# When this works, a real ticket from tickets.jsonl prints a reply on
# the student default model, classify prints a route by itself, and
# pytest on tests/test_dataflow_v1.py is green.

# %%
from pathlib import Path
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.v1_triage import build_v1_triage, classify
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
ticket = json.loads(tickets_path.read_text(encoding="utf-8").splitlines()[0])
print("ticket_id", ticket["ticket_id"])
print("text", ticket["text"])
print("model", config.CHAT_MODEL)

# %%
graph = build_v1_triage()
state = graph.invoke({"ticket": ticket["text"]})
print("state_after")
print("route", state.get("route"))
print("order", state.get("order"))
print("reply", state.get("reply"))

# %%
alone = classify({"ticket": ticket["text"]})
print("classify_alone_route", alone.get("route"))

# %%
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_dataflow_v1.py", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", result.returncode)
