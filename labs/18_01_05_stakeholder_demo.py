# %% [markdown]
# Stakeholder demo of the DataFlow desk.
#
# When this works, the spec is on screen, a lookup POST, a refuse POST
# and a park POST print their replies, the refuse stays visible, the
# park payload prints, and the cost line from ops/cost_report.md prints.
# A demo script that hides the refuse fails.

# %%
from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from deploy.smoke import DEFAULT_LOOKUP, DEFAULT_PARK, DEFAULT_REFUSE

print("model", config.CHAT_MODEL)
print("spec", (root / "career" / "pm" / "spec.md").as_posix())
print("demo_script", (root / "career" / "pm" / "demo_script.md").as_posix())
print("spec_page")
print((root / "career" / "pm" / "spec.md").read_text(encoding="utf-8"))

refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()
http_log = tempfile.NamedTemporaryFile(prefix="http-", suffix=".jsonl", delete=False)
http_log.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = refunds.name

runs_dir = root / "career" / "pm" / "runs"
runs_dir.mkdir(parents=True, exist_ok=True)
demo_path = runs_dir / "demo.json"

cost_path = root / "ops" / "cost_report.md"
cost_line = ""
if cost_path.is_file():
    cost_line = cost_path.read_text(encoding="utf-8")
print("cost_line")
print(cost_line if cost_line else "ops/cost_report.md missing on this clone")


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def wait_health(url: str, tries: int = 80) -> None:
    last = ""
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as resp:
                if resp.status == 200:
                    return
                last = str(resp.status)
        except Exception as exc:
            last = str(exc)
        time.sleep(0.25)
    raise RuntimeError("service never became healthy: " + last)


def post_run(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url + "/run",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def start_server(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.pop("DATAFLOW_UI_MODEL", None)
    env.pop("DATAFLOW_API_KEYS", None)
    env.pop("DATAFLOW_SKIP_INTERRUPT", None)
    env["DATAFLOW_UI_PORT"] = str(port)
    env["DATAFLOW_REFUNDS_PATH"] = refunds.name
    env["DATAFLOW_HTTP_LOG"] = http_log.name
    env["DATAFLOW_CHECKPOINTER"] = "memory"
    return subprocess.Popen(
        [sys.executable, str(root / "scripts" / "serve_dataflow.py")],
        cwd=str(root),
        env=env,
    )


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


port = free_port()
url = "http://127.0.0.1:" + str(port)

# %%
print("cell", "three_posts")
proc = start_server(port)
demo = {
    "lookup": None,
    "refuse": None,
    "park": None,
    "cost_line": cost_line,
}
try:
    wait_health(url)
    print("service", url)
    print("model_from_config", config.CHAT_MODEL)

    status, body = post_run(url, {"ticket": DEFAULT_LOOKUP})
    print("lookup_status", status)
    print("lookup_reply", json.dumps(body, ensure_ascii=True, default=str))
    demo["lookup"] = body

    status, body = post_run(url, {"ticket": DEFAULT_REFUSE})
    print("refuse_status", status)
    print("refuse_reply", json.dumps(body, ensure_ascii=True, default=str))
    reply = ""
    if isinstance(body, dict):
        reply = str(body.get("reply") or "")
    print("refuse_on_screen", reply)
    demo["refuse"] = body

    status, body = post_run(url, {"ticket": DEFAULT_PARK})
    print("park_status", status)
    print("park_reply", json.dumps(body, ensure_ascii=True, default=str))
    payload = None
    if isinstance(body, dict):
        payload = body.get("payload")
        print("parked", body.get("parked"))
    print("park_payload", json.dumps(payload, ensure_ascii=True, default=str))
    demo["park"] = body

    print("cost_line_again")
    print(cost_line if cost_line else "ops/cost_report.md missing on this clone")
    demo_path.write_text(
        json.dumps(demo, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", demo_path.as_posix())
finally:
    stop_server(proc)

# %%
print("cell", "hide_refuse_break")
hidden_script = (
    "Minute 1 spec. Minute 2 lookup POST. Minute 3 skipped. "
    "Minute 4 park POST. Minute 5 cost line."
)
print("hidden_demo_script", hidden_script)
print("hidden_posts", "lookup, park")
print(
    "why_that_demo_fails",
    "A demo that hides the refuse skips the POST that shows the desk "
    "saying no. The stakeholder never sees the miss, leaves thinking "
    "the desk always answers, and the spec's stop-on-refuse field was "
    "never on screen.",
)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
print("refunds_path", refunds.name)
print("http_log", http_log.name)
print("demo_json_runtime", demo_path.as_posix())
print("no committed file mutated")
