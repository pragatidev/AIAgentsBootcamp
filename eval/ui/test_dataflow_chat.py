"""Playwright tests for the thin DataFlow chat page.

The customer sees a citation, a REFUSE, and a parked refund. A green
handler is not a rendered page.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def read_answer_early(page) -> str:
    """Planted flake: read the answer div right after clicking Send, before the stream ends."""
    return page.locator("#answer").inner_text()


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _wait_health(url: str, tries: int = 40) -> None:
    last = ""
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as resp:
                if resp.status == 200:
                    return
                last = str(resp.status)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = str(exc)
        time.sleep(0.25)
    raise RuntimeError("dataflow ui did not become healthy: " + last)


def _skip_if_playwright_missing() -> None:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as exc:
        pytest.skip("playwright is not installed: " + str(exc))
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as player:
            browser = player.chromium.launch(headless=True)
            browser.close()
    except Exception as exc:
        pytest.skip("playwright chromium is missing: " + str(exc))


@pytest.fixture(scope="session")
def chat_server():
    _skip_if_playwright_missing()
    port = _free_port()
    env = os.environ.copy()
    env["DATAFLOW_UI_MODEL"] = "fixture"
    env["DATAFLOW_UI_PORT"] = str(port)
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "serve_dataflow.py")],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = "http://127.0.0.1:" + str(port)
    try:
        _wait_health(url)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def page(chat_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as player:
        browser = player.chromium.launch(headless=True)
        pg = browser.new_page()
        pg.goto(chat_server)
        yield pg
        browser.close()


def test_policy_question_shows_citation(page) -> None:
    page.fill("#q", "What is the customer return window?")
    page.click("#send")
    page.locator(".citation").wait_for(timeout=15_000)
    text = page.locator(".citation").inner_text()
    assert "return_policy.md" in text.replace("\\", "/")


def test_unknown_question_refuses(page) -> None:
    page.fill("#q", "Do you sell coffee beans in the DataFlow shop?")
    page.click("#send")
    page.locator(".refuse").wait_for(timeout=15_000)
    assert "REFUSE" in page.locator(".refuse").inner_text()


def test_parked_refund_shows_parked(page) -> None:
    page.fill("#q", "Please refund order DF-1001. The desk lamp is unused.")
    page.click("#send")
    page.locator(".parked").wait_for(timeout=15_000)
    assert "parked" in page.locator(".parked").inner_text().lower()
