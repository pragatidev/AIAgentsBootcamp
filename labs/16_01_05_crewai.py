# %% [markdown]
# CrewAI: business analysis crew on the DataFlow ticket.
#
# When this works, two agents both send the customer reply. Lock the
# reply to the writer and one reply prints. You gain a crew metaphor.
# You lose interrupt, reducers and time travel.

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

run_path = root / "labs" / "16_crewai" / "runs" / "crew_run.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""
crew_py = root / "labs" / "16_crewai" / "crew.py"
crewai_py = Path(r"D:\project\viralLoom\.venv_crewai\Scripts\python.exe")

print("model", config.CHAT_MODEL)
print("base_url", config.OLLAMA_BASE_URL)
print("crewai_interpreter", str(crewai_py))
print("crewai_interpreter_exists", crewai_py.is_file())

GAIN = "a crew metaphor: researcher, policy lookup, and writer as roles"
LOSS = "no interrupt, no reducers, no time travel"


def run_crew(lock_writer: bool) -> tuple[int, str, str]:
    interpreter = crewai_py if crewai_py.is_file() else Path(sys.executable)
    args = [str(interpreter), str(crew_py)]
    if lock_writer:
        args.append("--lock-writer")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    env["PYTHONIOENCODING"] = "utf-8"
    env["CREWAI_TRACING_ENABLED"] = "false"
    proc = subprocess.run(
        args,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    return proc.returncode, proc.stdout, proc.stderr


def parse_json_stdout(text: str):
    text = (text or "").strip()
    if not text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        return None


payload: dict = {
    "model": config.CHAT_MODEL,
    "base_url": config.OLLAMA_BASE_URL,
    "gain": GAIN,
    "lose": LOSS,
}

# %%
print("cell", "break")
print("BREAK: two agents both send the customer reply")
if not crewai_py.is_file():
    print("BLOCKED ON CREWAI")
    print("missing interpreter", str(crewai_py))
    payload["blocked"] = True
    payload["blocked_on"] = "CREWAI"
    payload["error"] = "missing interpreter " + str(crewai_py)

code, out, err = run_crew(lock_writer=False)
print("plant_returncode", code)
print("plant_stdout")
print(out[-3000:])
if err.strip():
    print("plant_stderr")
    print(err[-1500:])
plant = parse_json_stdout(out)
payload["plant"] = plant or {"stdout": out[-2000:], "stderr": err[-1000:], "returncode": code}
if plant:
    print("plant_reply_count", plant.get("reply_count"))
    print("plant_final", str(plant.get("final") or "")[:400])

# %%
print("cell", "fix")
print("FIX: lock the reply to the writer")
code, out, err = run_crew(lock_writer=True)
print("fix_returncode", code)
print("fix_stdout")
print(out[-3000:])
if err.strip():
    print("fix_stderr")
    print(err[-1500:])
fixed = parse_json_stdout(out)
payload["fix"] = fixed or {"stdout": out[-2000:], "stderr": err[-1000:], "returncode": code}
if fixed:
    print("fix_reply_count", fixed.get("reply_count"))
    print("fix_order_row", fixed.get("order_row"))
    print("fix_policy_line", fixed.get("policy_line"))
    print("fix_final", str(fixed.get("final") or "")[:500])

print("rubric_row_crewai")
print("gain", GAIN)
print("lose", LOSS)

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
print("restored_crew_run", bool(committed_run))
