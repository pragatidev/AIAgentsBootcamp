# %% [markdown]
# Monday smoke test for the deployed agent.
#
# When this works, smoke with the park assertion removed shows a refund
# would go live, then with the assertion smoke prints green.

# %%
from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from deploy.smoke import run_smoke

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


def start_server(port: int, extra: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env["DATAFLOW_UI_MODEL"] = "fixture"
    env["DATAFLOW_UI_PORT"] = str(port)
    env["DATAFLOW_REFUNDS_PATH"] = refunds.name
    env.pop("DATAFLOW_API_KEYS", None)
    env.pop("DATAFLOW_SKIP_INTERRUPT", None)
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
print("cell", "skip_park_would_go_live")
proc = start_server(port, {"DATAFLOW_SKIP_INTERRUPT": "1"})
try:
    wait_health(url)
    print("smoke_skip_park")
    code = run_smoke(url, skip_park=True)
    print("skip_park_exit", code)
    print("refunds_path", refunds.name)
    if Path(refunds.name).is_file():
        print("refund_rows", Path(refunds.name).read_text(encoding="utf-8"))
    print("smoke_with_park_assertion_against_live_write")
    code = run_smoke(url, skip_park=False)
    print("park_assertion_against_skip_interrupt_exit", code)
finally:
    stop_server(proc)

# %%
print("cell", "smoke_green")
proc = start_server(port)
try:
    wait_health(url)
    code = run_smoke(url, skip_park=False)
    print("smoke_exit", code)
finally:
    stop_server(proc)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
print("no committed file mutated")
