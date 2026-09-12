"""7.3 miss-to-test. Red on the old desk, green with the control."""

from pathlib import Path
import json

import pytest

from dataflow.agent.harness_loop import proposals_from_run, run_desk
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel

ROOT = Path(__file__).resolve().parents[1]
FAILING = ROOT / "harness" / "runs" / "failing_ticket.json"
TICKET = "You billed me twice for order DF-1010. Please reverse the extra charge."


def _double_script(run: dict) -> list[dict]:
    """Replay saved proposals. If the live model only issued one refund,
    duplicate that issue_refund so the unguarded desk still writes twice.
    The saved run's note records that honesty; this is the miss the control holds.
    """
    props = proposals_from_run(run)
    issues = [p for p in props if p["tool"] == "issue_refund"]
    if len(issues) >= 2:
        return props
    script = [p for p in props if p["tool"] != "stop"]
    if issues:
        extra = dict(issues[0])
        extra["reason"] = (extra.get("reason") or "duplicate charge") + " (second write)"
        script.append(extra)
    script.append(
        {"tool": "stop", "order_id": "DF-1010", "amount": 0.0, "reason": "done"}
    )
    return script


def _model_from_failing() -> FakeChatModel:
    run = json.loads(FAILING.read_text(encoding="utf-8"))
    return FakeChatModel(structured={"DeskAction": _double_script(run)})


@pytest.mark.xfail(strict=True, reason="the old desk refunds twice; red on purpose")
def test_double_refund_red_on_old_desk(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    run = json.loads(FAILING.read_text(encoding="utf-8"))
    assert run.get("ticket_id") == "T-3005"
    out = run_desk(
        run.get("ticket") or TICKET,
        model=_model_from_failing(),
        max_steps=8,
        cap_enabled=True,
        guide_mode="none",
        sensor_enabled=False,
        guarded=False,
        permissions_enabled=False,
    )
    assert out["refund_count"] == 1


def test_double_refund_green_with_control(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    run = json.loads(FAILING.read_text(encoding="utf-8"))
    out = run_desk(
        run.get("ticket") or TICKET,
        model=_model_from_failing(),
        max_steps=8,
        cap_enabled=True,
        guarded=True,
    )
    assert out["refund_count"] == 1
    assert out["refunds"][0]["order_id"] == "DF-1010"
