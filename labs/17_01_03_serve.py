# %% [markdown]
# Serve DataFlow with FastAPI.
#
# When this works, health is ok, a free-text POST 422s, a real ticket
# prints a thread_id and a reply, and deploy/runs/first_request.json is saved.

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

print("model", config.CHAT_MODEL)
print("cue", "dataflow/serve/app.py focus /health")
print("cue", "dataflow/serve/app.py focus class ")

refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = refunds.name


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


def post(url: str, data: bytes, content_type: str = "application/json"):
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = raw
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return exc.code, dict(exc.headers), body


port = free_port()
env = os.environ.copy()
env.pop("DATAFLOW_UI_MODEL", None)
env.pop("DATAFLOW_API_KEYS", None)
env["DATAFLOW_UI_PORT"] = str(port)
env["DATAFLOW_CHECKPOINTER"] = "memory"
env["DATAFLOW_REFUNDS_PATH"] = refunds.name
proc = subprocess.Popen(
    [sys.executable, str(root / "scripts" / "serve_dataflow.py")],
    cwd=str(root),
    env=env,
)
url = "http://127.0.0.1:" + str(port)
print("url", url)

# %%
print("cell", "health_and_422_and_ticket")
try:
    wait_health(url)
    status, _headers, body = (
        urllib.request.urlopen(url + "/health", timeout=5).status,
        {},
        json.loads(urllib.request.urlopen(url + "/health", timeout=5).read().decode("utf-8")),
    )
    print("health", status, body)

    code, headers, err = post(url + "/run", b'"just a string"')
    print("free_text_status", code)
    print("free_text_body", err)

    ticket = "What is the customer return window?"
    code, headers, out = post(
        url + "/run",
        json.dumps({"ticket": ticket}).encode("utf-8"),
    )
    print("ticket_status", code)
    print("thread_id", out.get("thread_id") if isinstance(out, dict) else None)
    print("reply", out.get("reply") if isinstance(out, dict) else out)
    print("parked", out.get("parked") if isinstance(out, dict) else None)

    dest = root / "deploy" / "runs" / "first_request.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print("wrote", dest.as_posix())
    print(dest.read_text(encoding="utf-8"))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
print("first_request.json is gitignored runtime output")
print("git_status_note leave it; gitignore covers deploy/runs/*.json")
