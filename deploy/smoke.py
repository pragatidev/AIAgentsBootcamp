"""Monday smoke test for the DataFlow door.

Health, one lookup, one refuse, one park. Each asserted unless --skip-park.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_LOOKUP = "Where is order DF-1002? Tracking still says in transit."
DEFAULT_REFUSE = "Do you sell coffee beans in the DataFlow shop?"
DEFAULT_PARK = "Please refund order DF-1001. The desk lamp is unused."


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("DATAFLOW_SMOKE_KEY", "").strip()
    if key:
        headers["x-api-key"] = key
    actor = os.environ.get("DATAFLOW_SMOKE_ACTOR", "").strip()
    if actor:
        headers["x-actor-id"] = actor
    return headers


def _get(url: str) -> tuple[int, Any]:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def _post(url: str, payload: dict[str, Any]) -> tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def run_smoke(base: str, *, skip_park: bool = False) -> int:
    base = base.rstrip("/")
    failures: list[str] = []

    status, body = _get(base + "/health")
    print("health", status, body)
    if status != 200 or not (isinstance(body, dict) and body.get("ok") is True):
        failures.append("health")

    status, body = _post(base + "/run", {"ticket": DEFAULT_LOOKUP})
    print("lookup", status, body)
    if status != 200 or not (isinstance(body, dict) and body.get("thread_id")):
        failures.append("lookup")
    elif isinstance(body, dict) and body.get("parked"):
        failures.append("lookup_parked")

    status, body = _post(base + "/run", {"ticket": DEFAULT_REFUSE})
    print("refuse", status, body)
    reply = ""
    if isinstance(body, dict):
        reply = str(body.get("reply") or "")
    refused = "I do not have that in the knowledge base" in reply or (
        isinstance(body, dict) and body.get("route") == "refuse"
    )
    if status != 200:
        failures.append("refuse")
    elif not refused:
        failures.append("refuse_miss")

    status, body = _post(base + "/run", {"ticket": DEFAULT_PARK})
    print("park", status, body)
    parked = isinstance(body, dict) and bool(body.get("parked"))
    if skip_park:
        if parked:
            print("skip_park assertion off; refund parked anyway")
        else:
            print("refund would go live")
            if isinstance(body, dict):
                print("park_reply", body.get("reply"))
    else:
        if status != 200 or not parked:
            failures.append("park")
            print("park_assertion FAIL")
        else:
            print("park_assertion PASS")

    if failures:
        print("smoke red", failures)
        return 1
    print("smoke green")
    print("stop_reason grep: parked" if not skip_park else "stop_reason grep skipped")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DATAFLOW_SMOKE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--skip-park", action="store_true")
    args = parser.parse_args()
    return run_smoke(args.base_url, skip_park=args.skip_park)


if __name__ == "__main__":
    raise SystemExit(main())
