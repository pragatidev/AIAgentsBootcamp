# %% [markdown]
# Test the DataFlow agent UI with Playwright.
#
# When this works, the early innerText read is printed five times, two
# Playwright tests go green, and a screenshot of the policy answer sits
# at eval/ui/screens/policy_citation.png.

# %%
from pathlib import Path
import os
import socket
import subprocess
import sys
import time
import urllib.request

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from eval.ui.test_dataflow_chat import read_answer_early

print("model", config.CHAT_MODEL)


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def wait_health(url: str, tries: int = 60) -> None:
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("ui never became healthy at " + url)


port = free_port()
env = os.environ.copy()
env.pop("DATAFLOW_UI_MODEL", None)
env["DATAFLOW_UI_PORT"] = str(port)
proc = subprocess.Popen(
    [sys.executable, str(root / "scripts" / "serve_dataflow.py")],
    cwd=str(root),
    env=env,
)
url = "http://127.0.0.1:" + str(port)
print("url", url)
wait_health(url)

# %%
print("cell", "early_innertext")
from playwright.sync_api import sync_playwright

screen_dir = root / "eval" / "ui" / "screens"
screen_dir.mkdir(parents=True, exist_ok=True)
screen_path = screen_dir / "policy_citation.png"
early_reads = []
with sync_playwright() as player:
    browser = player.chromium.launch(headless=True)
    page = browser.new_page()
    for i in range(5):
        page.goto(url)
        page.fill("#q", "What is the customer return window?")
        page.click("#send")
        seen = read_answer_early(page)
        early_reads.append(seen)
        print("early_read", i + 1, repr(seen[:200]))
        page.locator(".citation").wait_for(timeout=120_000)
        if i == 0:
            page.screenshot(path=str(screen_path), full_page=True)
            print("screenshot", screen_path.as_posix())
    browser.close()

complete = [row for row in early_reads if "30 days" in row or "return" in row.lower()]
if len(complete) == len(early_reads):
    print("early_read_complete_every_time", True)
    print("the early read happened to be complete every time; not faked")
else:
    print("early_read_complete_every_time", False)
    print("early_read_partial_count", len(early_reads) - len(complete))

proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()

# %%
print("cell", "two_tests_green")
result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "eval/ui/test_dataflow_chat.py::test_policy_question_shows_citation",
        "eval/ui/test_dataflow_chat.py::test_unknown_question_refuses",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(result.stdout)
print(result.stderr)
print("pytest_exit", result.returncode)
