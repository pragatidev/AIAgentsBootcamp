"""7.2 guide and sensor controls. Pytest stays green with no live model."""

from harness.sensors.refund_diff import refund_diff
from harness.sensors.schema_assert import SchemaError, schema_assert
from dataflow.agent.harness_loop import run_desk
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel


def test_refund_diff_fail_on_duplicate():
    row = {"refunded": True, "order_id": "DF-1010", "amount": 22.0, "reason": "dup"}
    out = refund_diff([row], [row, dict(row)], "DF-1010")
    assert out["verdict"] == "FAIL"
    assert "FAIL" in out["message"]
    assert "DF-1010" in out["message"]


def test_refund_diff_pass_on_one_row():
    row = {"refunded": True, "order_id": "DF-1010", "amount": 22.0, "reason": "dup"}
    out = refund_diff([], [row], "DF-1010")
    assert out["verdict"] == "PASS"
    assert "PASS" in out["message"]


def test_schema_assert_raises_on_missing_amount():
    try:
        schema_assert({"order_id": "DF-1010", "reason": "dup"})
        raised = False
    except SchemaError as exc:
        raised = True
        assert exc.field == "amount"
        assert "amount" in str(exc)
    assert raised


def test_guided_loop_issues_one_refund(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    model = FakeChatModel(
        structured={
            "DeskAction": [
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
                    "reason": "already refunded",
                },
            ]
        }
    )
    out = run_desk(
        "You billed me twice for order DF-1010. Please reverse the extra charge.",
        model=model,
        max_steps=6,
        cap_enabled=True,
        guide_mode="tight",
    )
    assert out["refund_count"] == 1
    assert out["refunds"][0]["order_id"] == "DF-1010"
