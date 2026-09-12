"""Live pings. Skip without a key or a local server. Never invent stdout."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import config


def ping_hosted(prompt: str = "ping") -> dict:
    if not config.has_live_key():
        return {"skipped": True, "reason": "no cloud key"}
    return {
        "skipped": True,
        "reason": "hosted ping is recorded at lecture time. ids live in config.py",
        "model": config.OPENAI_CHAT_MODEL or config.ANTHROPIC_CHAT_MODEL,
    }


def ping_local(prompt: str = "ping") -> dict:
    url = config.OLLAMA_BASE_URL.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return {
            "skipped": False,
            "model": config.CHAT_MODEL,
            "base": config.OLLAMA_BASE_URL,
            "models_endpoint": json.loads(body) if body.startswith("{") or body.startswith("[") else body[:200],
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {"skipped": True, "reason": "no local model"}
