"""Lab 06.00.04 (9.4), the rubric probes. A scripted classifier stands in for the real model here, and only here: in
this process through config, in the two child processes through tests/fixtures/lg_r1.py's sitecustomize."""

import contextlib
import io
import runpy
from pathlib import Path

import pytest

import config
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import scripted_children

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_00_04_rubric_probe.py"


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    """One run of the lab (it starts two child processes), shared by the tests below."""
    tmp_path = tmp_path_factory.mktemp("rubric")
    repo_ledger = refund_mod.REFUNDS_PATH
    before = repo_ledger.read_bytes() if repo_ledger.exists() else None
    buffer = io.StringIO()
    with pytest.MonkeyPatch.context() as monkeypatch, contextlib.redirect_stdout(buffer):
        # The lab points DATAFLOW_REFUNDS_PATH at its own temp file; setting it here first makes monkeypatch put it back.
        monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "unused.jsonl"))
        scripted_children(tmp_path, monkeypatch, route="refund")
        model = FakeChatModel(structured={"HitlDecision": [{"route": "refund"}, {"route": "lookup"}]})
        monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
        runpy.run_path(str(LAB), run_name="__main__")
    after = repo_ledger.read_bytes() if repo_ledger.exists() else None
    assert after == before, "the lab wrote the repo's own refunds.jsonl"
    return buffer.getvalue().splitlines()


def _probe(out, name):
    i = out.index(next(line for line in out if line.startswith(f"PROBE {name} ")))
    return out[i], out[i + 1]


def test_four_probes_pass_and_the_fifth_is_named(out):
    assert [line for line in out if line.startswith("PROBE ")] == [
        "PROBE park PASS",
        "PROBE survive_kill PASS",
        "PROBE test_one_decision PASS",
        "PROBE see_every_step PASS",
        "PROBE change_it NOT RUN HERE: Section 18, change a graph while threads are live",
    ]


def test_park_evidence(out):
    _, evidence = _probe(out, "park")
    assert evidence.startswith("evidence route refund, next ('refund',), the reviewer is asked: Approve this refund of ")
    assert "on order DF-1001?" in evidence
    assert evidence.endswith("refunds.jsonl rows 0")


def test_survive_kill_evidence(out):
    _, evidence = _probe(out, "survive_kill")
    assert "parked at ['refund'] and died; process " in evidence
    assert "found it waiting at ['refund'], resumed with approve: Refund issued for order DF-1001." in evidence
    assert evidence.endswith("refunds.jsonl rows 1")
    payload = next(line for line in out if line.startswith("parked payload "))
    assert '"order_id": "DF-1001"' in payload and '"action": "refund"' in payload


def test_one_decision_and_every_step(out):
    _, evidence = _probe(out, "test_one_decision")
    assert evidence == (
        "evidence pick_route alone: {'refund': 'refund', 'lookup': 'lookup', 'policy': 'policy', 'billing': 'lookup', '': 'lookup'}"
    )
    _, evidence = _probe(out, "see_every_step")
    assert evidence == "evidence nodes in order: classify -> lookup"
    assert [line.split()[1] for line in out if line.startswith("step ")] == ["classify", "lookup"]
