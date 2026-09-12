# %% [markdown]
# Write the test that fails, then passes after the control.
#
# When this works, pytest shows red then green and the failure log
# entry is closed. The first assertion checks a log string the control
# never prints; the fix asserts on the refund count.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config

test_path = root / "tests" / "test_harness_control.py"
log_path = root / "harness" / "failure_log.md"
print("model", config.CHAT_MODEL)
print("test_path", test_path.as_posix())

WRONG = '''"""Wrong assertion: a log string the control never prints."""

def test_double_refund_green_with_control():
    log = "desk finished"
    # This string is never printed by the control, so the test passes
    # even on the old desk that refunds twice.
    assert "refund_control_ok" not in log
'''

# %%
print("cell", 1)
print("writing_wrong_assertion")
test_path.write_text(WRONG, encoding="utf-8")
wrong_run = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("wrong_exit", wrong_run.returncode)
print("wrong_stdout")
print(wrong_run.stdout)
print("wrong_stderr")
print(wrong_run.stderr)
print("passed_for_the_wrong_reason", wrong_run.returncode == 0)

# %%
print("cell", 2)
print("writing_refund_count_tests")
GOOD = test_path.read_text(encoding="utf-8")  # placeholder, replaced below
GOOD = r'''"""7.3 miss-to-test. Red on the old desk, green with the control."""

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
'''
test_path.write_text(GOOD, encoding="utf-8")
print("wrote_good_tests", test_path.as_posix())

good_run = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("good_exit", good_run.returncode)
print("good_stdout")
print(good_run.stdout)
print("good_stderr")
print(good_run.stderr)

# %%
print("cell", 3)
text = log_path.read_text(encoding="utf-8")
old = "closed by:"
new = (
    "closed by: harness/guides/no_repeat_refund.md "
    "and tests/test_harness_control.py"
)
if old in text:
    text = text.replace(old, new, 1)
else:
    text = text.rstrip() + "\n" + new + "\n"
log_path.write_text(text, encoding="utf-8")
print("wrote", log_path.as_posix())
print(log_path.read_text(encoding="utf-8"))
