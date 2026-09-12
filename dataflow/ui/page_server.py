"""Launch a Streamlit page, prove it serves, screenshot, then kill it."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def launch_streamlit(
    script: str | Path,
    port: int,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen:
    script_path = Path(script)
    if not script_path.is_absolute():
        script_path = ROOT / script_path
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(script_path),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def wait_http(url: str, tries: int = 60) -> None:
    last = ""
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
                last = str(resp.status)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = str(exc)
        time.sleep(0.5)
    raise RuntimeError("streamlit page never served at " + url + " last=" + last)


def fetch_root(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return int(resp.status), body


def screenshot_url(url: str, dest: Path, wait_text: str = "DataFlow") -> Path:
    from playwright.sync_api import sync_playwright

    dest.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as player:
        browser = player.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.get_by_text(wait_text).first.wait_for(timeout=30_000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(dest), full_page=True)
        browser.close()
    return dest


def stop_proc(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def run_page_shot(
    script: str | Path,
    dest: Path,
    extra_env: dict[str, str] | None = None,
    wait_text: str = "DataFlow",
) -> dict[str, Any]:
    """Launch headless Streamlit, GET /, screenshot, kill. Always kills."""
    port = free_port()
    url = "http://127.0.0.1:" + str(port)
    proc = launch_streamlit(script, port, extra_env=extra_env)
    out: dict[str, Any] = {"url": url, "port": port, "status": None, "screenshot": None}
    try:
        wait_http(url)
        status, body = fetch_root(url)
        out["status"] = status
        out["body_len"] = len(body)
        out["body_head"] = body[:180].replace("\n", " ")
        shot = screenshot_url(url, dest, wait_text=wait_text)
        out["screenshot"] = str(shot.as_posix())
        return out
    finally:
        stop_proc(proc)
