# %% [markdown]
# Cost and latency per request.
#
# When this works, ops/cost_report.md lists tokens, ms, and the model id.
# A stuffed ticket is expensive and must show up. Hide it and the report
# lies. Append the fat row with a one-line note. No dollar amounts.

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
from dataflow.ops.cost import write_cost_report

print("model", config.CHAT_MODEL)

refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()
http_log = root / "ops" / "tracing" / "runs" / "http.jsonl"
report_path = root / "ops" / "cost_report.md"
http_log.parent.mkdir(parents=True, exist_ok=True)
committed_http = http_log.read_bytes() if http_log.is_file() else b""
committed_report = report_path.read_bytes() if report_path.is_file() else b""


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
    env["DATAFLOW_UI_PORT"] = str(port)
    env["DATAFLOW_REFUNDS_PATH"] = refunds.name
    env["DATAFLOW_HTTP_LOG"] = str(http_log)
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


thin = "What is the customer return window?"
stuffed = (
    "Pasted thread from the customer. " * 80
    + "Still asking: What is the customer return window after all of that?"
)
print("stuffed_chars", len(stuffed))

port = free_port()
url = "http://127.0.0.1:" + str(port)
proc = start_server(port)

# %%
print("cell", "two_requests_and_reports")
try:
    wait_health(url)
    if http_log.is_file():
        http_log.write_text("", encoding="utf-8")
    code, body = post_run(url, {"ticket": thin})
    print("thin_status", code)
    print("thin_reply", (body.get("reply") if isinstance(body, dict) else body))
    code, body = post_run(url, {"ticket": stuffed})
    print("fat_status", code)
    print("fat_reply", (body.get("reply") if isinstance(body, dict) else body))
    print("fat_chars_sent", len(stuffed))

    hidden = write_cost_report(http_log, report_path, hide_fat=True)
    print("hidden_report")
    print(hidden)
    print("hiding_makes_the_report_lie", "fat" not in hidden.split("fat row")[0] or "hidden_fat_rows" in hidden)

    full = write_cost_report(
        http_log,
        report_path,
        hide_fat=False,
        note="stuffed pasted thread; was hidden, now appended",
    )
    print("full_report")
    print(full)
    print("dollar_in_report", "$" in full)
finally:
    stop_server(proc)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_http:
    http_log.write_bytes(committed_http)
elif http_log.is_file():
    print("http_jsonl gitignored")
if committed_report:
    report_path.write_bytes(committed_report)
    print("restored_cost_report", True)
elif report_path.is_file():
    print("cost_report.md is gitignored runtime output")
