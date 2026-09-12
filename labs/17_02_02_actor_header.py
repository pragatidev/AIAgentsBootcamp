# %% [markdown]
# Put an actor id on POST /run.
#
# When this works: no key is 401; a good key with an actor off the
# allowlist is refused at the tool; a good key with a reviewer parks
# the refund and the actor prints on the trace line. The break removes
# the header check and a stranger reaches the graph.

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
print("cue", "dataflow/serve/app.py focus x-api-key")

refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()


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


def post_run(url: str, payload: dict, headers: dict | None = None):
    data = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url + "/run", data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def start_server(port: int, extra: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env["DATAFLOW_UI_MODEL"] = "fixture"
    env["DATAFLOW_UI_PORT"] = str(port)
    env["DATAFLOW_API_KEYS"] = "desk-key:reviewer-1,other-key:reviewer-2"
    env["DATAFLOW_REFUNDS_PATH"] = refunds.name
    env.pop("DATAFLOW_SKIP_API_KEY", None)
    if extra:
        env.update(extra)
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
proc = start_server(port)
ticket = "Please refund order DF-1001. The desk lamp is unused."

# %%
print("cell", "three_requests")
try:
    wait_health(url)
    code, body = post_run(url, {"ticket": ticket})
    print("no_key_status", code)
    print("no_key_body", body)

    code, body = post_run(
        url,
        {"ticket": ticket},
        {"x-api-key": "desk-key", "x-actor-id": "stranger"},
    )
    print("off_allowlist_status", code)
    print("off_allowlist_reply", body.get("reply") if isinstance(body, dict) else body)
    print("off_allowlist_payload", body.get("payload") if isinstance(body, dict) else None)

    code, body = post_run(
        url,
        {"ticket": ticket},
        {"x-api-key": "desk-key", "x-actor-id": "reviewer-1"},
    )
    print("reviewer_status", code)
    print("reviewer_parked", body.get("parked") if isinstance(body, dict) else None)
    print("reviewer_actor", body.get("actor") if isinstance(body, dict) else None)
    print("reviewer_payload", body.get("payload") if isinstance(body, dict) else body)
finally:
    stop_server(proc)

# %%
print("cell", "break_skip_header")
time.sleep(0.5)
port = free_port()
url = "http://127.0.0.1:" + str(port)
proc = start_server(port, {"DATAFLOW_SKIP_API_KEY": "1"})
try:
    wait_health(url)
    code, body = post_run(url, {"ticket": "Where is order DF-1002?"})
    print("stranger_reaches_graph_status", code)
    print("stranger_thread", body.get("thread_id") if isinstance(body, dict) else None)
    print("stranger_reply", body.get("reply") if isinstance(body, dict) else body)
finally:
    stop_server(proc)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
print("no committed file mutated")
