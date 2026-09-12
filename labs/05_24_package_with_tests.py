# %% [markdown]
# Move the TechCorp agent into the package with tests.
#
# When this works, the package imports, one ticket runs, and
# pytest tests/test_techcorp_*.py is green. The break is a module
# that calls the model at import.

# %%
from pathlib import Path
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from techcorp.agent.desk import build_techcorp_desk, run_ticket

print("model", config.CHAT_MODEL)
print("imported", "techcorp.agent.desk")

desk = build_techcorp_desk(middleware=[])
out = run_ticket(
    desk,
    "Ticket TC-1002 for employee E-4102: VPN connects then drops every few minutes.",
    user_id="E-4102",
    thread_id="lab-5-24-one-ticket",
)
messages = out.get("messages") or []
print("ticket_ran", bool(messages))
print("final", getattr(messages[-1], "content", None) if messages else None)

# %%
proc = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_techcorp_tools.py",
        "tests/test_techcorp_desk.py",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=root,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("pytest_stdout")
print(proc.stdout)
print("pytest_stderr")
print(proc.stderr)
print("exit_code", proc.returncode)

# %%
print("BREAK: a module that calls the model at import")
planted = root / "labs" / "_planted_model_at_import.py"
planted.write_text(
    "import time\n"
    "from config import get_chat_model\n"
    "STARTED = time.perf_counter()\n"
    "MODEL = get_chat_model()\n"
    "REPLY = MODEL.invoke('ping from import')\n"
    "ELAPSED = time.perf_counter() - STARTED\n",
    encoding="utf-8",
)
started = time.perf_counter()
try:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "planted_model_at_import", planted
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    elapsed = time.perf_counter() - started
    print("import_elapsed_s", elapsed)
    print("module_elapsed_s", getattr(module, "ELAPSED", None))
    print("import_reply", getattr(module, "REPLY", None))
    print("import_made_model_call", True)
    print("the import itself made a model call before any test could run")
except Exception as err:
    elapsed = time.perf_counter() - started
    print("import_elapsed_s", elapsed)
    print("import_error_type", type(err).__name__)
    print("import_error", err)
    print("the import itself made a model call or errored before any test could run")
finally:
    planted.unlink(missing_ok=True)
    print("plant_removed", not planted.exists())
