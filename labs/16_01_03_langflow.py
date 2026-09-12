# %% [markdown]
# Langflow: visual DataFlow ticket, then export to code.
#
# When this works, the export runs with an empty tool schema and the
# model cannot call lookup. Fill the schema from dataflow.tools.orders,
# and the policy line plus the order row print. The lab drives the
# export with the Langflow interpreter as a subprocess.

# %%
from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.tools.orders import lookup_order

run_path = root / "labs" / "16_langflow" / "runs" / "export_run.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""
exported = root / "labs" / "16_langflow" / "exported.py"
flow_path = root / "labs" / "16_langflow" / "flow.json"

langflow_py = Path(r"D:\project\viralLoom\.venv_langflow\Scripts\python.exe")
print("model", config.CHAT_MODEL)
print("base_url", config.OLLAMA_BASE_URL)
print("langflow_interpreter", str(langflow_py))
print("langflow_interpreter_exists", langflow_py.is_file())
print("flow_json", flow_path.as_posix())
print("exported_py", exported.as_posix())

schema_obj = getattr(lookup_order, "tool_call_schema", None) or getattr(
    lookup_order, "args_schema", None
)
print("orders_schema")
if schema_obj is not None and hasattr(schema_obj, "model_json_schema"):
    print(json.dumps(schema_obj.model_json_schema(), indent=2)[:800])
else:
    print(schema_obj)


def run_export(fill_schema: bool) -> tuple[int, str, str]:
    interpreter = langflow_py if langflow_py.is_file() else Path(sys.executable)
    args = [str(interpreter), str(exported)]
    if fill_schema:
        args.append("--fill-schema")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        args,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
    )
    return proc.returncode, proc.stdout, proc.stderr


payload: dict = {
    "model": config.CHAT_MODEL,
    "base_url": config.OLLAMA_BASE_URL,
    "interpreter": str(langflow_py),
}

# %%
print("cell", "break")
print("BREAK: export as first exported has an empty tool schema")
if not langflow_py.is_file():
    print("BLOCKED ON LANGFLOW")
    print("missing interpreter", str(langflow_py))
    payload["blocked"] = True
    payload["blocked_on"] = "LANGFLOW"
    payload["error"] = "missing interpreter " + str(langflow_py)
    print("falling back to shared interpreter", sys.executable)

code, out, err = run_export(fill_schema=False)
print("plant_returncode", code)
print("plant_stdout")
print(out)
if err.strip():
    print("plant_stderr")
    print(err[:2000])
plant = None
if out.strip().startswith("{"):
    try:
        plant = json.loads(out)
    except json.JSONDecodeError:
        plant = None
payload["plant"] = plant or {"stdout": out[-2000:], "stderr": err[-1000:], "returncode": code}
if plant:
    print("plant_lookup_called", plant.get("lookup_called"))
    print("plant_order_row", plant.get("order_row"))
    print("plant_policy_line", plant.get("policy_line"))

# %%
print("cell", "fix")
print("FIX: add the schema from dataflow.tools.orders")
code, out, err = run_export(fill_schema=True)
print("fix_returncode", code)
print("fix_stdout")
print(out)
if err.strip():
    print("fix_stderr")
    print(err[:2000])
fixed = None
if out.strip().startswith("{"):
    try:
        fixed = json.loads(out)
    except json.JSONDecodeError:
        fixed = None
payload["fix"] = fixed or {"stdout": out[-2000:], "stderr": err[-1000:], "returncode": code}
if fixed:
    print("fix_lookup_called", fixed.get("lookup_called"))
    print("fix_order_row", fixed.get("order_row"))
    print("fix_policy_line", fixed.get("policy_line"))
    print("fix_reply", (fixed.get("reply") or "")[:500])

run_path.parent.mkdir(parents=True, exist_ok=True)
run_path.write_text(
    json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
    encoding="utf-8",
)
print("wrote", run_path.as_posix())

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_run:
    run_path.write_text(committed_run, encoding="utf-8")
print("restored_export_run", bool(committed_run))
