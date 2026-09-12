# %% [markdown]
# Wire PostgresSaver and resume a parked DataFlow refund.
#
# When this works, a refund parks, the process is killed, resume without
# thread_id starts over, the same thread_id still prints the parked payload.
# Postgres is tried once. BLOCKED ON DOCKER when the URL is unreachable.
# SQLite proves the same kill-and-resume shape.

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
print("cue", "dataflow/serve/app.py focus PostgresSaver")

refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()
sqlite_path = root / "dataflow" / "data" / "serve_checkpoints.sqlite"
http_log = tempfile.NamedTemporaryFile(prefix="http-", suffix=".jsonl", delete=False)
http_log.close()


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


def post_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
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
    env["DATAFLOW_CHECKPOINTER"] = "sqlite"
    env["DATAFLOW_SQLITE_PATH"] = str(sqlite_path)
    env["DATAFLOW_REFUNDS_PATH"] = refunds.name
    env["DATAFLOW_HTTP_LOG"] = http_log.name
    return subprocess.Popen(
        [sys.executable, str(root / "scripts" / "serve_dataflow.py")],
        cwd=str(root),
        env=env,
    )


def stop_server(proc: subprocess.Popen) -> None:
    proc.kill()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    time.sleep(0.5)


# %%
print("cell", "postgres_import_and_reach")
from langgraph.checkpoint.postgres import PostgresSaver

print("imported_PostgresSaver", PostgresSaver.__name__)
pg_url = os.environ.get(
    "DATAFLOW_PG_URL",
    "postgresql://dataflow:dataflow@localhost:5432/dataflow",
)
print("trying_postgres", pg_url)
try:
    import psycopg

    conn = psycopg.connect(pg_url, connect_timeout=2)
    conn.close()
    print("postgres_reachable", True)
except Exception as exc:
    print("BLOCKED ON DOCKER")
    print("postgres_error", type(exc).__name__ + ":", exc)
    print("sqlite_fallback proving the same kill-and-resume shape")

# %%
print("cell", "kill_and_resume_sqlite")
for extra in ("", "-wal", "-shm", ".meta.json"):
    leftover = Path(str(sqlite_path) + extra)
    if leftover.exists():
        leftover.unlink()
sqlite_path.parent.mkdir(parents=True, exist_ok=True)

port = free_port()
proc = start_server(port)
url = "http://127.0.0.1:" + str(port)
print("url", url)
ticket = "Please refund order DF-1001. The desk lamp is unused."
try:
    wait_health(url)
    code, parked = post_json(url + "/run", {"ticket": ticket})
    print("park_status", code)
    print("parked", parked.get("parked") if isinstance(parked, dict) else None)
    print("park_thread", parked.get("thread_id") if isinstance(parked, dict) else None)
    print("park_payload", parked.get("payload") if isinstance(parked, dict) else parked)
    tid = parked.get("thread_id") if isinstance(parked, dict) else None
    print("killing_process", proc.pid)
    stop_server(proc)
    proc = None
    print("restarting")
    time.sleep(0.5)
    port = free_port()
    url = "http://127.0.0.1:" + str(port)
    print("restart_url", url)
    proc = start_server(port)
    wait_health(url)
    code, fresh = post_json(url + "/run", {"ticket": ticket})
    print("without_thread_status", code)
    print(
        "without_thread_id",
        fresh.get("thread_id") if isinstance(fresh, dict) else None,
    )
    print(
        "without_thread_starts_over",
        (fresh.get("thread_id") if isinstance(fresh, dict) else None) != tid,
    )
    code, same = post_json(url + "/run", {"thread_id": tid})
    print("with_thread_status", code)
    print("with_thread_parked", same.get("parked") if isinstance(same, dict) else None)
    print("with_thread_payload", same.get("payload") if isinstance(same, dict) else same)
    print(
        "same_thread",
        (same.get("thread_id") if isinstance(same, dict) else None) == tid,
    )
finally:
    if proc is not None:
        stop_server(proc)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
time.sleep(1.0)
for extra in ("", "-wal", "-shm", ".meta.json"):
    leftover = Path(str(sqlite_path) + extra)
    if leftover.exists():
        try:
            leftover.unlink()
        except OSError as exc:
            print("unlink_blocked", leftover.name, exc)
print("removed sqlite sidecar")
