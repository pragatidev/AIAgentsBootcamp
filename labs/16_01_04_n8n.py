# %% [markdown]
# n8n: the same DataFlow ticket with no code.
#
# When this works, the webhook fires twice on one ticket and two
# replies come back. Add a unique ticket id and a dedupe node so the
# second run skips. n8n is started as a subprocess and killed in finally.

# %%
from pathlib import Path
import copy
import http.cookiejar
import json
import os
import shutil
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

TICKET = (
    "Hi, I want to return order DF-1001. The desk lamp is unused. "
    "Can I get a refund?"
)

run_path = root / "labs" / "16_n8n" / "runs" / "n8n_run.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""
workflow_path = root / "labs" / "16_n8n" / "dataflow_ticket.json"

print("model", config.CHAT_MODEL)
print("base_url", config.OLLAMA_BASE_URL)
print("workflow", workflow_path.as_posix())


def fill_workflow(raw: dict) -> dict:
    text = json.dumps(raw)
    orders = str(root / "dataflow" / "data" / "orders.json").replace("\\", "/")
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    text = text.replace("__ORDERS_PATH__", orders)
    text = text.replace("__OLLAMA_URL__", base)
    text = text.replace("__CHAT_MODEL__", config.CHAT_MODEL)
    return json.loads(text)


def add_dedupe(flow: dict) -> dict:
    flow = copy.deepcopy(flow)
    node = {
        "parameters": {
            "jsCode": (
                "const staticData = $getWorkflowStaticData('global');\n"
                "const item = $input.first().json;\n"
                "const body = item.body || item;\n"
                "const ticketId = String(body.ticket_id || '');\n"
                "if (!staticData.seen) { staticData.seen = {}; }\n"
                "if (ticketId && staticData.seen[ticketId]) {\n"
                "  return [{ json: { skipped: true, ticket_id: ticketId, "
                "reply: 'duplicate skipped' } }];\n"
                "}\n"
                "if (ticketId) { staticData.seen[ticketId] = true; }\n"
                "return [{ json: item }];\n"
            )
        },
        "id": "dedupe-1",
        "name": "Dedupe",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [120, 0],
    }
    flow["nodes"].insert(1, node)
    flow["connections"]["Webhook"] = {
        "main": [[{"node": "Dedupe", "type": "main", "index": 0}]]
    }
    flow["connections"]["Dedupe"] = {
        "main": [
            [
                {"node": "Lookup order", "type": "main", "index": 0},
            ]
        ]
    }
    flow["name"] = "DataFlow ticket deduped"
    return flow


def port_open(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR))
BROWSER_ID = "dataflow-ticket-lab"


def http_json(url: str, payload: dict | None = None, method: str = "GET", headers: dict | None = None, timeout: int = 60):
    data = None
    hdrs = {
        "Accept": "application/json",
        "browser-id": BROWSER_ID,
    }
    if headers:
        hdrs.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
        method = method if method != "GET" else "POST"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        if not raw:
            return {"status": resp.status}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw, "status": resp.status}


def workflow_id(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    if payload.get("id"):
        return str(payload["id"])
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    return ""


def kill_tree(proc: subprocess.Popen) -> None:
    handle = getattr(proc, "_n8n_log_handle", None)
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
        )
    else:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
    if handle is not None:
        try:
            handle.close()
        except Exception:
            pass


def start_n8n(user_folder: Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["N8N_USER_FOLDER"] = str(user_folder)
    env["N8N_PORT"] = str(port)
    env["N8N_HOST"] = "127.0.0.1"
    env["N8N_LISTEN_ADDRESS"] = "127.0.0.1"
    env["N8N_PROTOCOL"] = "http"
    env["WEBHOOK_URL"] = "http://127.0.0.1:" + str(port) + "/"
    env["N8N_SECURE_COOKIE"] = "false"
    env["N8N_DIAGNOSTICS_ENABLED"] = "false"
    env["N8N_PERSONALIZATION_ENABLED"] = "false"
    env["N8N_VERSION_NOTIFICATIONS_ENABLED"] = "false"
    env["N8N_HIRING_BANNER_ENABLED"] = "false"
    env["N8N_RUNNERS_ENABLED"] = "false"
    env["NODE_FUNCTION_ALLOW_BUILTIN"] = "fs,path"
    env["N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS"] = "false"
    env["N8N_RESTRICT_FILE_ACCESS_TO"] = str(root)
    npx = shutil.which("npx") or "npx"
    args = [npx, "--yes", "n8n"]
    print("n8n_cmd", args)
    print("n8n_user_folder", str(user_folder))
    creation = 0
    if os.name == "nt":
        creation = subprocess.CREATE_NEW_PROCESS_GROUP
    log_path = user_folder / "n8n_server.log"
    log_handle = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        args,
        cwd=str(root),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation,
    )
    proc._n8n_log_handle = log_handle  # type: ignore[attr-defined]
    proc._n8n_log_path = log_path  # type: ignore[attr-defined]
    return proc


payload: dict = {
    "model": config.CHAT_MODEL,
    "base_url": config.OLLAMA_BASE_URL,
    "ticket": TICKET,
}
proc = None
user_folder = None
port = 5678

# %%
print("cell", "start")
try:
    user_folder = Path(tempfile.mkdtemp(prefix="n8n-dataflow-"))
    if port_open("127.0.0.1", port):
        raise RuntimeError("port " + str(port) + " already in use")
    proc = start_n8n(user_folder, port)
    ready = False
    deadline = time.time() + 420
    while time.time() < deadline:
        if proc.poll() is not None:
            log_tail = ""
            path = getattr(proc, "_n8n_log_path", None)
            if path and Path(path).is_file():
                log_tail = Path(path).read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError("n8n exited " + str(proc.returncode) + "\n" + log_tail)
        if port_open("127.0.0.1", port):
            ready = True
            break
        time.sleep(0.5)
    if not ready:
        log_tail = ""
        path = getattr(proc, "_n8n_log_path", None)
        if path and Path(path).is_file():
            log_tail = Path(path).read_text(encoding="utf-8", errors="replace")[-2000:]
        raise RuntimeError("n8n did not open port " + str(port) + "\n" + log_tail)
    print("n8n_ready", True)
    base = "http://127.0.0.1:" + str(port)
    rest_deadline = time.time() + 90
    while time.time() < rest_deadline:
        try:
            probe = http_json(base + "/healthz")
            print("healthz", probe)
            if isinstance(probe, dict) and probe.get("status") == "ok":
                break
            if isinstance(probe, dict) and "starting" in json.dumps(probe).lower():
                time.sleep(2)
                continue
            break
        except Exception as exc:
            print("healthz_wait", type(exc).__name__, str(exc)[:120])
            time.sleep(2)
    else:
        raise RuntimeError("n8n healthz never became ok")
    try:
        http_json(
            base + "/rest/owner/setup",
            {
                "email": "desk@dataflow.local",
                "firstName": "Data",
                "lastName": "Flow",
                "password": "DataFlowDesk1",
            },
        )
        print("owner_setup", True)
    except Exception as exc:
        print("owner_setup_note", type(exc).__name__, str(exc)[:200])
    login = None
    login_error = None
    for _ in range(12):
        for body in (
            {"email": "desk@dataflow.local", "password": "DataFlowDesk1"},
            {"emailOrLdapLoginId": "desk@dataflow.local", "password": "DataFlowDesk1"},
        ):
            try:
                login = http_json(base + "/rest/login", body)
                blob = json.dumps(login).lower()
                if "starting" in blob:
                    login_error = RuntimeError(blob[:200])
                    login = None
                    continue
                break
            except Exception as exc:
                login_error = exc
                login = None
        if login is not None:
            break
        time.sleep(3)
    if login is None:
        raise RuntimeError("login failed: " + str(login_error)[:400])
    print("login_keys", list(login)[:8] if isinstance(login, dict) else type(login).__name__)

    raw = json.loads(workflow_path.read_text(encoding="utf-8"))
    plant_flow = fill_workflow(raw)
    created = None
    for attempt in range(12):
        created = http_json(base + "/rest/workflows", plant_flow)
        print("import_attempt", attempt + 1, json.dumps(created)[:200])
        if workflow_id(created):
            break
        blob = json.dumps(created).lower()
        if "starting" in blob:
            time.sleep(3)
            continue
        break
    wid = workflow_id(created or {})
    print("workflow_id", wid)
    if not wid:
        raise RuntimeError("import returned no id: " + json.dumps(created)[:500])
    http_json(base + "/rest/workflows/" + wid, {**created, "active": True}, method="PATCH")
    print("activated_plant", True)
    time.sleep(1)
    webhook = base + "/webhook/dataflow-ticket"
    print("cell", "break")
    print("BREAK: webhook fires twice on one ticket")
    replies = []
    for i in range(2):
        row = http_json(webhook, {"ticket": TICKET}, timeout=180)
        replies.append(row)
        print("plant_reply", i + 1, json.dumps(row)[:400])
    payload["plant_replies"] = replies
    payload["plant_reply_count"] = len(replies)

    print("cell", "fix")
    print("FIX: unique ticket id plus a dedupe node, second run skips")
    http_json(base + "/rest/workflows/" + wid, {**created, "active": False}, method="PATCH")
    deduped = add_dedupe(plant_flow)
    created2 = http_json(base + "/rest/workflows", deduped)
    wid2 = workflow_id(created2)
    print("deduped_workflow_id", wid2)
    http_json(base + "/rest/workflows/" + wid2, {**created2, "active": True}, method="PATCH")
    time.sleep(1)
    body = {"ticket": TICKET, "ticket_id": "T-DF-1001"}
    first = http_json(webhook, body, timeout=180)
    second = http_json(webhook, body, timeout=180)
    print("fix_first", json.dumps(first)[:400])
    print("fix_second", json.dumps(second)[:400])
    payload["fix_first"] = first
    payload["fix_second"] = second
    payload["second_skipped"] = bool(
        isinstance(second, dict) and (second.get("skipped") or "duplicate" in json.dumps(second).lower())
    )
    print("second_skipped", payload["second_skipped"])
except Exception as exc:
    print("BLOCKED ON N8N")
    print(type(exc).__name__)
    print(str(exc)[:2000])
    payload["blocked"] = True
    payload["blocked_on"] = "N8N"
    payload["error"] = type(exc).__name__ + ": " + str(exc)[:2000]
    help_cmd = shutil.which("npx") or "npx"
    try:
        dry = subprocess.run(
            [help_cmd, "--yes", "n8n", "execute", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        print("n8n_execute_help_returncode", dry.returncode)
        print((dry.stdout or "")[:600])
        print((dry.stderr or "")[:300])
        payload["n8n_execute_help"] = (dry.stdout or dry.stderr or "")[:600]
    except Exception as help_exc:
        print("n8n_execute_help_error", type(help_exc).__name__, str(help_exc)[:400])
finally:
    if proc is not None:
        kill_tree(proc)
        print("n8n_killed", True)
    if user_folder is not None and user_folder.exists():
        shutil.rmtree(user_folder, ignore_errors=True)
        print("n8n_user_folder_removed", True)

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
print("restored_n8n_run", bool(committed_run))
