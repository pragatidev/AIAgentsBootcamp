# %% [markdown]
# Wire the tracer into FastAPI.
#
# When this works, a POST with the real model writes a trace row with the
# request id next to the DataFlow spans. The break drops the id from the
# tracer context and two concurrent requests land without ids.

# %%
from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config

print("model", config.CHAT_MODEL)
print("cue", "dataflow/serve/app.py focus request_id")

refunds = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
refunds.close()
http_log = root / "ops" / "tracing" / "runs" / "http.jsonl"
http_log.parent.mkdir(parents=True, exist_ok=True)
committed_http = http_log.read_bytes() if http_log.is_file() else b""


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
        with urllib.request.urlopen(req, timeout=180) as resp:
            headers = dict(resp.headers)
            return resp.status, headers, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return exc.code, dict(exc.headers or {}), body


def start_server(port: int, extra: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env.pop("DATAFLOW_UI_MODEL", None)
    env.pop("DATAFLOW_API_KEYS", None)
    env["DATAFLOW_UI_PORT"] = str(port)
    env["DATAFLOW_REFUNDS_PATH"] = refunds.name
    env["DATAFLOW_HTTP_LOG"] = str(http_log)
    env.pop("DATAFLOW_DROP_REQUEST_ID", None)
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


def last_http_row() -> dict:
    if not http_log.is_file():
        return {}
    lines = [ln for ln in http_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return {}
    return json.loads(lines[-1])


def print_trace(path: str, request_id: str) -> None:
    p = Path(path)
    print("trace_path", path)
    if not p.is_file():
        print("trace_missing", True)
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        print(
            "span",
            row.get("kind"),
            row.get("name"),
            "request_id",
            row.get("request_id"),
            "ms",
            row.get("duration_ms"),
        )
        if request_id and row.get("request_id") == request_id:
            print("joined_request_id", request_id)


port = free_port()
url = "http://127.0.0.1:" + str(port)

# %%
print("cell", "post_with_request_id")
proc = start_server(port)
try:
    wait_health(url)
    code, headers, body = post_run(
        url, {"ticket": "Where is order DF-1002? Tracking still says in transit."}
    )
    rid = headers.get("x-request-id") or headers.get("X-Request-Id")
    print("status", code)
    print("response_request_id", rid)
    print("thread_id", body.get("thread_id") if isinstance(body, dict) else None)
    print("reply", body.get("reply") if isinstance(body, dict) else body)
    row = last_http_row()
    print("http_row_request_id", row.get("request_id"))
    print("http_row_ms", row.get("ms"))
    print("http_row_tokens", row.get("tokens"))
    print_trace(str(row.get("trace_path") or ""), str(rid or ""))
finally:
    stop_server(proc)

# %%
print("cell", "break_drop_request_id")
proc = start_server(port, {"DATAFLOW_DROP_REQUEST_ID": "1"})
try:
    wait_health(url)
    results: list[dict] = []

    def knock(label: str) -> None:
        code, headers, body = post_run(
            url, {"ticket": "Where is order DF-1002? " + label}
        )
        results.append(
            {
                "label": label,
                "status": code,
                "header_id": headers.get("x-request-id") or headers.get("X-Request-Id"),
                "body": body,
            }
        )

    t1 = threading.Thread(target=knock, args=("A",))
    t2 = threading.Thread(target=knock, args=("B",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    print("concurrent_results", json.dumps(results, default=str)[:2000])
    if http_log.is_file():
        lines = [
            json.loads(ln)
            for ln in http_log.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        last_two = lines[-2:]
        for row in last_two:
            print(
                "dropped_row",
                "http_request_id",
                row.get("request_id"),
                "trace_path",
                row.get("trace_path"),
            )
            path = Path(str(row.get("trace_path") or ""))
            if path.is_file():
                ids = []
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    span = json.loads(line)
                    ids.append(span.get("request_id"))
                print("span_request_ids", ids)
                print("spans_without_ids", all(not item for item in ids))
finally:
    stop_server(proc)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_http:
    http_log.write_bytes(committed_http)
    print("restored_http_jsonl", True)
elif http_log.is_file():
    print("http_jsonl is gitignored runtime output")
