# %% [markdown]
# Critic a TalentFlow outreach draft.
#
# When this works, the miss list prints and the revised mail contains
# the fact. The break is a critic that always returns empty. The fix
# is the fixture draft with a missing role title.

# %%
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from talentflow.graphs.critic import build_critic
from talentflow.graphs.score_resumes import load_resumes

print("model", config.CHAT_MODEL)

loaded = load_resumes()
row = next(r for r in loaded["resumes"] if r["name"] == "Sarah Chen")
payload = {
    "name": row["name"],
    "resume": row["text"],
    "job": loaded["job"],
}
print("candidate", payload["name"])

graph = build_critic()
out = graph.invoke(payload)
draft = str(out.get("draft") or "")
misses = list(out.get("misses") or [])
revision = str(out.get("revision") or "")
print("draft")
print(draft)
print("miss_list")
for item in misses:
    print(item)
print("revision")
print(revision)
if not misses:
    print(
        "real_critic_found_no_miss",
        "fixture test carries the proof",
    )

# %%
print("cell", "break")
print("BREAK: planted critic always returns empty")
planted_graph = build_critic(plant_empty=True)
planted = planted_graph.invoke(payload)
planted_draft = str(planted.get("draft") or "")
planted_misses = list(planted.get("misses") or [])
planted_revision = str(planted.get("revision") or "")
print("planted_draft")
print(planted_draft)
print("planted_miss_list", planted_misses)
print("planted_revision")
print(planted_revision)
print("revision_equals_draft", planted_revision == planted_draft)

# %%
print("cell", "fix")
print("FIX: fixture draft missing the role title must produce a miss")
pytest_cmd = [
    sys.executable,
    "-m",
    "pytest",
    "tests/test_critic.py",
    "-q",
    "--override-ini",
    "addopts=",
]
red_env = os.environ.copy()
red_env["TALENTFLOW_PLANT_EMPTY_CRITIC"] = "1"
red = subprocess.run(
    pytest_cmd,
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
    env=red_env,
)
print("planted_pytest_stdout")
print(red.stdout)
print("planted_pytest_stderr")
print(red.stderr)
print("planted_pytest_exit", red.returncode)

green = subprocess.run(
    pytest_cmd,
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("committed_pytest_stdout")
print(green.stdout)
print("committed_pytest_stderr")
print(green.stderr)
print("committed_pytest_exit", green.returncode)
