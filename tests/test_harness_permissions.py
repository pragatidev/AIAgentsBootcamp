"""7.3 refund write permissions. Pytest stays green with no live model."""

from dataflow.agent.harness_loop import run_desk
from dataflow.tools import refund as refund_mod
from harness.permissions import ALLOWED_REFUND_ACTORS
from tests.fixtures.fake_model import FakeChatModel

TICKET = "You billed me twice for order DF-1010. Please reverse the extra charge."

SCRIPT = [
    {
        "tool": "lookup_order",
        "order_id": "DF-1010",
        "amount": 0.0,
        "reason": "",
    },
    {
        "tool": "issue_refund",
        "order_id": "DF-1010",
        "amount": 22.0,
        "reason": "duplicate charge",
    },
    {
        "tool": "stop",
        "order_id": "DF-1010",
        "amount": 0.0,
        "reason": "done",
    },
]


def _model():
    return FakeChatModel(structured={"DeskAction": [dict(item) for item in SCRIPT]})


def test_actor_off_list_blocked(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    out = run_desk(
        TICKET,
        model=_model(),
        max_steps=6,
        permissions_enabled=True,
        actor_id="customer-C-2010",
    )
    assert "customer-C-2010" not in ALLOWED_REFUND_ACTORS
    assert out["refund_count"] == 0
    assert not path.exists()
    blocked = [s for s in out["steps"] if s.get("blocked")]
    assert blocked
    assert "customer-C-2010" in blocked[0]["blocked"]["message"]
    assert "issue_refund" in blocked[0]["blocked"]["message"]


def test_actor_on_list_passes(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    out = run_desk(
        TICKET,
        model=_model(),
        max_steps=6,
        permissions_enabled=True,
        actor_id="reviewer-1",
    )
    assert "reviewer-1" in ALLOWED_REFUND_ACTORS
    assert out["refund_count"] == 1
    assert path.is_file()
    assert out["refunds"][0]["order_id"] == "DF-1010"
