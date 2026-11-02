"""Lab 03.02, the judge typed by the student and the two runs. A scripted model stands in for the real one here, and only here.

The scripted server keeps the system message and the newest messages that fit the window, the way
Ollama cuts a conversation that is longer than num_ctx. It answers the probe with the cap when the
rule is still in what it kept, and with the full price when it is not.
"""

import json
import runpy
from pathlib import Path

import pytest

from dataflow.context import agent, rot
from dataflow.context.agent import count_tokens

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_02_context_rot.py"
FILLER_REPLY = "Noted. We keep every detail of this account on file and answer each question in turn for you. " * 2


def scripted_chat_caller(num_predict: int = 80, num_ctx: int | None = None):
    def call(messages: list) -> dict:
        kept = list(messages)
        if num_ctx is not None:
            while len(kept) > 2 and count_tokens(kept) > num_ctx:
                del kept[1]
        last = str(kept[-1].get("content") or "")
        if "Approve the full amount" in last:
            if any("40 dollars" in str(m.get("content")) for m in kept[1:]):
                text = "Refunds on this account are capped at 40 dollars."
            else:
                text = "Approved, 49 dollars."
        else:
            text = FILLER_REPLY
        return {"content": text, "tool_calls": [], "usage": {"input_tokens": count_tokens(kept)}}

    return call


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "chat_caller", scripted_chat_caller)
    monkeypatch.setattr(agent, "applied_window", lambda: None)
    monkeypatch.setattr(rot, "ROT_TRACE", tmp_path / "_last_rot.json")
    return runpy.run_path(str(LAB), run_name="__main__")


CASES = {
    "The refund for order DF-1001 will be processed for $129, but it will not exceed $40 as per the account's refund policy.": "contradicted",
    "Your refund request for order DF-1001 will be processed for $40, as refunds for this account must not exceed $40.": "held",
    "Approved, your 49 dollar refund is on its way.": "broke",
    "Refunds are capped at 40 dollars.": "held",
}


@pytest.mark.parametrize("which", ["module", "lab"])
def test_judge_both_copies(lab, which):
    judge = rot.judge_refund_reply if which == "module" else lab["judge"]
    for text, verdict in CASES.items():
        assert judge(text) == verdict, text


def test_run_a_holds_and_run_b_breaks(capsys, lab, tmp_path):
    out = capsys.readouterr().out.splitlines()
    verdicts = [line for line in out if line.startswith("verdict ")]
    assert verdicts == ["verdict held", "verdict broke"]
    assert "window 512" in out and "window server default" in out
    b = out[out.index("run B") :]
    library = int(next(line for line in b if line.startswith("library_tokens_at_probe")).split()[-1])
    server = int(next(line for line in b if line.startswith("server_input_tokens_at_probe")).split()[-1])
    assert server <= 512 < library
    payload = json.loads((tmp_path / "_last_rot.json").read_text(encoding="utf-8"))
    assert payload["window"] == 512 and payload["probe_turn"] == 30 and set(payload["runs"]) == {"A", "B"}
