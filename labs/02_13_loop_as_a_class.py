# %% [markdown]
# Turn the scratch loop into a class.
#
# ScratchAgent is run_loop built once: the model, the tools and the cap are
# settings, and run(ticket) is the same loop. One agent, two tickets, then
# the tests, which hand the class a scripted model and need no Ollama.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from techcorp.agent.scratch import (
    ScratchAgent,
    lookup_user,
    openai_caller,
    reset_password,
    tool_schema,
)

print("class", ScratchAgent.__name__)
print("method", ScratchAgent.run.__qualname__)

# %%
PASSWORD = (
    "TC-1001 user E-4101: I forgot my laptop password after the long "
    "weekend. Please reset it."
)
VPN = (
    "TC-1002 user E-4102: VPN connects then drops every few minutes "
    "from the home office. What is on this account?"
)
schema = [
    tool_schema("lookup_user", "Look up a TechCorp employee by user_id. Use this for account, VPN, or status questions."),
    tool_schema("reset_password", "Reset a TechCorp employee laptop password."),
]
agent = ScratchAgent(
    openai_caller(schema),
    {"lookup_user": lookup_user, "reset_password": reset_password},
    cap=8,
)
for ticket in (PASSWORD, VPN):
    out = agent.run(ticket)
    print("ticket", ticket.split(" ")[0])
    print("stop", out["stop"])
    print("final_answer", out["final"])
    for row in agent.rounds:
        print("round", row.get("round"), row.get("kind"), row.get("name") or "")

# %%
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_scratch_agent.py", "-q"],
    cwd=root,
    capture_output=True,
    text=True,
    check=False,
)
print(result.stdout + result.stderr, end="")
print("pytest_exit", result.returncode)
