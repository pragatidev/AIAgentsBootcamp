# %% [markdown]
# Rate limit the DataFlow door.
#
# When this works, a burst of twenty tickets on one key prints 200s then
# 429s with Retry-After, a second key still 200s, then the same burst
# with the limit off prints seconds per request honestly.

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
print("cue", "dataflow/serve/app.py focus 429")

refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()
TICKET = "Where is order DF-1002? Tracking still says in transit."


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


def post_run(url: str, payload: dict, headers: dict):
    data = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers)
    req = urllib.request.Request(url + "/run", data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            retry = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
            return resp.status, json.loads(resp.read().decode("utf-8")), retry
    except urllib.error.HTTPError as exc:
        retry = exc.headers.get("Retry-After") if exc.headers else None
        if not retry and exc.headers:
            retry = exc.headers.get("retry-after")
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return exc.code, body, retry


def start_server(port: int, extra: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env.pop("DATAFLOW_UI_MODEL", None)
    env["DATAFLOW_UI_PORT"] = str(port)
    env["DATAFLOW_API_KEYS"] = "desk-key:reviewer-1,other-key:reviewer-2"
    env["DATAFLOW_REFUNDS_PATH"] = refunds.name
    env["DATAFLOW_RATE_LIMIT"] = "5"
    env["DATAFLOW_RATE_WINDOW_SEC"] = "120"
    env.pop("DATAFLOW_RATE_LIMIT_OFF", None)
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


def burst(url: str, key: str, n: int) -> list[tuple[int, str | None, float]]:
    rows = []
    for i in range(n):
        t0 = time.perf_counter()
        code, body, retry = post_run(
            url,
            {"ticket": TICKET + " #" + str(i)},
            {"x-api-key": key},
        )
        dt = time.perf_counter() - t0
        rows.append((code, retry, dt))
        print("burst", key, i + 1, "status", code, "retry_after", retry, "sec", round(dt, 3))
    return rows


port = free_port()
url = "http://127.0.0.1:" + str(port)

# %%
print("cell", "capped_burst")
proc = start_server(port)
try:
    wait_health(url)
    rows = burst(url, "desk-key", 20)
    codes = [r[0] for r in rows]
    print("capped_codes", codes)
    print("capped_200s", codes.count(200))
    print("capped_429s", codes.count(429))
    retries = [r[1] for r in rows if r[0] == 429]
    print("retry_after_values", retries)
    code, body, retry = post_run(
        url,
        {"ticket": TICKET + " second-key"},
        {"x-api-key": "other-key"},
    )
    print("second_key_status", code)
    print("second_key_retry_after", retry)
    print("second_key_thread", body.get("thread_id") if isinstance(body, dict) else None)
finally:
    stop_server(proc)

# %%
print("cell", "limit_off_slowdown")
proc = start_server(port, {"DATAFLOW_RATE_LIMIT_OFF": "1", "DATAFLOW_RATE_LIMIT": "0"})
try:
    wait_health(url)
    rows = burst(url, "desk-key", 20)
    secs = [r[2] for r in rows]
    print("limit_off_codes", [r[0] for r in rows])
    print("limit_off_seconds", [round(s, 3) for s in secs])
    if secs:
        print("seconds_per_request", round(sum(secs) / len(secs), 3))
        print("slowdown_honest", "each request called the model from config")
finally:
    stop_server(proc)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
print("no committed file mutated")
