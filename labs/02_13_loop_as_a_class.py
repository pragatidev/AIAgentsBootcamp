# %% [markdown]
# Turn the scratch loop into a class.
#
# ScratchAgent.run(ticket) is the same behaviour, importable, tested.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from techcorp.agent.scratch import (
    ScratchAgent,
    openai_caller,
    reset_password,
    tool_schema,
)

print("class", ScratchAgent.__name__)
print("method", "run")

# %%
TICKET = (
    "TC-1001 user E-4101: I forgot my laptop password after the long "
    "weekend. Please reset it."
)
schema = [tool_schema("reset_password", "Reset a TechCorp employee laptop password.")]
agent = ScratchAgent(
    openai_caller(schema),
    {"reset_password": reset_password},
    cap=8,
)
out = agent.run(TICKET)
print("stop", out["stop"])
print("final_answer", out["final"])
for row in out["rounds"]:
    print("round", row.get("round"), row.get("kind"), row.get("name") or "")

# %%
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_scratch_agent.py", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", result.returncode)
