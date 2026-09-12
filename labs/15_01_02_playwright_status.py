# %% [markdown]
# A Playwright tool on a TechCorp status page.
#
# When this works, the fixture server serves the outage line, the desk
# with the model from config.py reads it and answers "Is the VPN down?",
# a planted file:// read scrapes README.md, and the allowlist blocks
# that URL without opening a browser.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from techcorp.agent.desk import run_ticket
from techcorp.browser.playwright_tool import (
    OUTAGE_LINE,
    build_browser_desk,
    read_status_page,
    read_status_page_ungated,
    serve_fixtures,
)

print("model", config.CHAT_MODEL)
print("outage_line_expected", OUTAGE_LINE)

server = serve_fixtures()
print("base_url", server.base_url)
status_url = server.base_url + "/status.html"
print("status_url", status_url)


def content_text(msg) -> str:
    content = getattr(msg, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(content)


def tool_payloads(state: dict) -> list:
    rows = []
    for msg in state.get("messages") or []:
        kind = str(getattr(msg, "type", "") or msg.__class__.__name__).lower()
        if "tool" not in kind or "call" in kind:
            continue
        raw = getattr(msg, "content", "") or ""
        try:
            rows.append(json.loads(raw))
        except Exception:
            rows.append({"raw": raw})
    return rows


try:
    print("cell", "direct_tool")
    direct = read_status_page.invoke({"url": status_url})
    print("tool_outage", direct.get("outage"))
    print("tool_url", direct.get("url"))
    print("tool_blocked", direct.get("blocked"))

    print("cell", "desk")
    ticket = "Is the VPN down? Read the status page at " + status_url
    print("ticket", ticket)
    desk = build_browser_desk()
    out = run_ticket(desk, ticket)
    payloads = tool_payloads(out)
    print("tool_payloads", payloads)
    messages = out.get("messages") or []
    print("final_reply", content_text(messages[-1]) if messages else "")
    if payloads:
        print("outage_line_from_desk", payloads[0].get("outage"))
    else:
        print("outage_line_from_desk", None)
        print("the model did not call read_status_page on this run")

    print("cell", "break")
    file_url = (root / "README.md").resolve().as_uri()
    print("planted_file_url", file_url)
    scraped = read_status_page_ungated(file_url)
    page_text = str(scraped.get("page") or "")
    first = page_text.splitlines()[0] if page_text.strip() else ""
    print("scraped_first_line", first)
    print("ungated_blocked", scraped.get("blocked"))

    print("cell", "fix")
    missed = read_status_page.invoke({"url": file_url})
    print("allowlist_miss", missed)
    print("blocked", missed.get("blocked"))
    print("reason", missed.get("reason"))
finally:
    server.stop()
    print("server_stopped", True)
