"""Browser labs need a Chromium that `pip install` does not bring: `playwright install chromium`, once.

The clone contract is `pytest -q` green on a fresh install, so the browser tests skip with that instruction
until the browser is there, instead of failing a student on step one.
"""

from __future__ import annotations

from pathlib import Path

REASON = "browser not installed yet: run `playwright install chromium` once to enable the browser labs and tests"


def browser_ready() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return Path(p.chromium.executable_path).is_file()
    except Exception:
        return False
