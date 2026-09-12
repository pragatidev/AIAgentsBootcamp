# %% [markdown]
# Rollback and the on-call runbook.
#
# When this works, a broken service flag makes health 500, rolling back
# the flag makes health ok, the runbook prints, and an image retag is
# tried once. BLOCKED ON DOCKER if the daemon is down.

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

runbook = root / "deploy" / "RUNBOOK.md"
tenant = root / "deploy" / "second_tenant.md"
print("runbook_path", runbook.as_posix())
print(runbook.read_text(encoding="utf-8"))
print("rollback_row")
print(tenant.read_text(encoding="utf-8"))

refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def health(url: str) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(url + "/health", timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except Exception as exc:
        return 0, str(exc)


def wait_status(url: str, want: int, tries: int = 80) -> None:
    last = ""
    for _ in range(tries):
        code, body = health(url)
        last = str(code) + " " + str(body)
        if code == want:
            return
        time.sleep(0.25)
    raise RuntimeError("health never reached " + str(want) + ": " + last)


def start_server(port: int, extra: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env["DATAFLOW_UI_MODEL"] = "fixture"
    env["DATAFLOW_UI_PORT"] = str(port)
    env["DATAFLOW_REFUNDS_PATH"] = refunds.name
    env.pop("DATAFLOW_BROKEN_HEALTH", None)
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

# %%
print("cell", "broken_then_rollback")
proc = start_server(port, {"DATAFLOW_BROKEN_HEALTH": "1"})
try:
    wait_status(url, 500)
    code, body = health(url)
    print("broken_health", code, body)
    print("simulate_broken_deploy DATAFLOW_BROKEN_HEALTH=1")
finally:
    stop_server(proc)

proc = start_server(port)
try:
    wait_status(url, 200)
    code, body = health(url)
    print("rolled_back_health", code, body)
    data = json.dumps({"ticket": "Where is order DF-1002?"}).encode("utf-8")
    req = urllib.request.Request(
        url + "/run",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    print("rollback_post_status", 200)
    print("rollback_thread", out.get("thread_id"))
    print("runbook_is_health_plus_one_POST")
finally:
    stop_server(proc)

# %%
print("cell", "image_retag")
retag = subprocess.run(
    ["docker", "tag", "dataflow-desk:previous", "dataflow-desk:live"],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
print("docker_tag_exit", retag.returncode)
err = (retag.stderr or retag.stdout or "").strip()
if retag.returncode != 0:
    print("BLOCKED ON DOCKER")
    print("docker_error", err[:2000])
else:
    print("retag_ok", "dataflow-desk:previous -> dataflow-desk:live")

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
print("runbook and second_tenant.md were read, not rewritten")
