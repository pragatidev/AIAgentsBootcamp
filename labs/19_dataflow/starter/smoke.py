"""Smoke the FastAPI door. Fixture model. No live key."""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
for parent in [Path.cwd(), *HERE.parents]:
    if (parent / "config.py").is_file() and (parent / "dataflow").is_dir():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

DEFAULT_LOOKUP = "Where is order DF-1002? Tracking still says in transit."
DEFAULT_REFUSE = "Do you sell coffee beans in the DataFlow shop?"
DEFAULT_PARK = "Please refund order DF-1001. The desk lamp is unused."


def run_smoke_in_process() -> int:
    os.environ.setdefault("DATAFLOW_UI_MODEL", "fixture")
    from fastapi.testclient import TestClient

    import app as door

    if door.app is None:
        print("smoke red", ["no_app"])
        return 1
    failures: list[str] = []
    with TestClient(door.app) as client:
        status = client.get("/health")
        body = status.json()
        print("health", status.status_code, body)
        if status.status_code != 200 or not body.get("ok"):
            failures.append("health")

        lookup = client.post("/run", json={"ticket": DEFAULT_LOOKUP})
        print("lookup", lookup.status_code, lookup.json())
        if lookup.status_code != 200 or not lookup.json().get("thread_id"):
            failures.append("lookup")
        elif lookup.json().get("parked"):
            failures.append("lookup_parked")

        refuse = client.post("/run", json={"ticket": DEFAULT_REFUSE})
        print("refuse", refuse.status_code, refuse.json())
        reply = str(refuse.json().get("reply") or "")
        refused = "I do not have that in the knowledge base" in reply or refuse.json().get(
            "route"
        ) == "refuse"
        if refuse.status_code != 200:
            failures.append("refuse")
        elif not refused:
            failures.append("refuse_miss")

        park = client.post("/run", json={"ticket": DEFAULT_PARK})
        print("park", park.status_code, park.json())
        if park.status_code != 200 or not park.json().get("parked"):
            failures.append("park")
            print("park_assertion FAIL")
        else:
            print("park_assertion PASS")

    if failures:
        print("smoke red", failures)
        return 1
    print("smoke green")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_smoke_in_process())
