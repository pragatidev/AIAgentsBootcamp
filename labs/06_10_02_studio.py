# %% [markdown]
# Run the desk in Studio.
#
# Print langgraph.json, the command langgraph dev, then start the
# local Agent Server for 20 seconds with --no-browser. Capture the
# server URL and the Studio URL. List the two graphs. Studio clicks
# themselves are recorded by the founder on screen.

# %%
from pathlib import Path
import json
import re
import subprocess
import sys
import threading
import time
import urllib.request

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

cfg_path = root / "langgraph.json"
print("langgraph_json_path", cfg_path.as_posix())
print("langgraph_json")
print(cfg_path.read_text(encoding="utf-8"))

print("command", "langgraph dev")
print("capture_command", "langgraph dev --no-browser")

scripts = Path(sys.executable).resolve().parent
langgraph_exe = scripts / "langgraph.exe"
if not langgraph_exe.is_file():
    langgraph_exe = scripts / "langgraph"
print("langgraph_exe", langgraph_exe.as_posix())
print("exists", langgraph_exe.is_file())

cmd = [str(langgraph_exe), "dev", "--no-browser"]
print("argv", cmd)

lines: list[str] = []
lock = threading.Lock()


def _pump(proc: subprocess.Popen) -> None:
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip("\n")
        with lock:
            lines.append(line)
        print("dev", line)


proc = subprocess.Popen(
    cmd,
    cwd=str(root),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
    bufsize=1,
)
pump = threading.Thread(target=_pump, args=(proc,), daemon=True)
pump.start()

started = time.perf_counter()
ready = False
assistants_raw = ""
assistants_error = ""
names: list[str] = []

while time.perf_counter() - started < 20:
    if proc.poll() is not None:
        break
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:2024/ok",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=1) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print("health", resp.status, body)
            ready = True
            break
    except Exception:
        time.sleep(0.4)

if ready:
    try:
        payload = json.dumps({"limit": 20, "offset": 0}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:2024/assistants/search",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assistants_raw = resp.read().decode("utf-8", errors="replace")
            print("assistants_http", resp.status)
    except Exception as exc:
        assistants_error = type(exc).__name__ + ": " + str(exc)
        print("assistants_post_error", assistants_error)
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:2024/assistants/search",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                assistants_raw = resp.read().decode("utf-8", errors="replace")
                print("assistants_http_get", resp.status)
        except Exception as exc2:
            assistants_error = type(exc2).__name__ + ": " + str(exc2)
            print("assistants_get_error", assistants_error)
    if assistants_raw:
        print("assistants_raw", assistants_raw)
        try:
            parsed = json.loads(assistants_raw)
        except json.JSONDecodeError:
            parsed = None
        rows = []
        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict):
            rows = parsed.get("assistants") or parsed.get("items") or []
            if not rows and ("graph_id" in parsed or "name" in parsed):
                rows = [parsed]
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("graph_id") or "")
            graph_id = str(row.get("graph_id") or "")
            print("assistant_name", name)
            print("assistant_graph_id", graph_id)
            if name:
                names.append(name)
            elif graph_id:
                names.append(graph_id)
        if not names:
            try:
                from langgraph_sdk import get_sync_client

                client = get_sync_client(url="http://127.0.0.1:2024")
                found = client.assistants.search(limit=20)
                print("assistants_sdk", found)
                if isinstance(found, list):
                    for row in found:
                        if isinstance(row, dict):
                            name = str(row.get("name") or row.get("graph_id") or "")
                            print("assistant_name", name)
                            print("assistant_graph_id", row.get("graph_id"))
                            if name:
                                names.append(name)
                        else:
                            name = str(getattr(row, "name", "") or getattr(row, "graph_id", ""))
                            print("assistant_name", name)
                            if name:
                                names.append(name)
            except Exception as exc:
                print("assistants_sdk_error", type(exc).__name__ + ": " + str(exc))

remaining = 20 - (time.perf_counter() - started)
if remaining > 0 and proc.poll() is None:
    time.sleep(remaining)

if proc.poll() is None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)

pump.join(timeout=2)
elapsed = time.perf_counter() - started
print("elapsed_seconds", round(elapsed, 2))
print("returncode", proc.returncode)
print("ready", ready)
print("assistant_names", names)

ansi = re.compile(r"\x1b\[[0-9;]*m")
blob = ansi.sub("", "\n".join(lines))
urls = re.findall(r"https?://[^\s]+", blob)
print("urls")
for url in urls:
    print("url", url.rstrip(".,)"))

server_url = ""
studio_url = ""
for url in urls:
    cleaned = url.rstrip(".,)")
    if "2024" in cleaned and "studio" not in cleaned.lower() and not server_url:
        server_url = cleaned
    if "studio" in cleaned.lower() or "smith.langchain.com" in cleaned:
        studio_url = cleaned
print("server_url", server_url)
print("studio_url", studio_url)

if not ready:
    print("server_did_not_start")
    print("error_verbatim")
    print(blob if blob.strip() else "(no server output)")
