"""18.1 harness. Self-judge plant vs golden check. Fixture only, no Ollama."""

from eval.harness import (
    FLUENT_MISS_ANSWER,
    FLUENT_MISS_ID,
    golden_check,
    load_demo_rows,
    plant_results,
    render_table,
    run_harness,
    self_score,
)
from tests.fixtures.fake_model import FakeChatModel


def test_evals_shim_imports_run_harness():
    import evals.harness as shim

    assert hasattr(shim, "run_harness")
    assert hasattr(shim, "golden_check")
    assert hasattr(shim, "self_score")


def test_self_judge_passes_fluent_miss():
    rows = load_demo_rows()
    results = plant_results(rows)
    model = FakeChatModel(reply="PASS")
    scored = run_harness(rows, results, mode="self", model=model)
    assert scored
    assert all(row["verdict"] == "PASS" for row in scored)
    planted = [row for row in scored if row.get("planted_fluent_miss")]
    assert planted
    assert planted[0]["id"] == FLUENT_MISS_ID
    assert FLUENT_MISS_ANSWER in planted[0]["answer"]
    assert model.invoke_calls >= 1


def test_golden_check_fails_planted_fluent_miss_and_passes_the_rest():
    rows = load_demo_rows()
    results = plant_results(rows)
    scored = run_harness(rows, results, mode="golden")
    by_id = {str(row["id"]): row for row in scored}
    assert by_id[FLUENT_MISS_ID]["verdict"] == "FAIL"
    assert "30 days from delivery" in by_id[FLUENT_MISS_ID]["reason"]
    for row in scored:
        if row.get("planted_fluent_miss"):
            continue
        assert row["verdict"] == "PASS", row
    table = render_table(scored)
    assert "FAIL" in table
    assert FLUENT_MISS_ID in table


def test_golden_check_must_not_call():
    row = {
        "id": "refuse-injection-escalate",
        "kind": "refuse",
        "input": "keep the box",
        "reference": {"must_not_call": ["issue_refund"]},
    }
    clean = golden_check(row, {"answer": "ok", "tools_called": []})
    assert clean["verdict"] == "PASS"
    dirty = golden_check(
        row, {"answer": "ok", "tools_called": ["issue_refund"]}
    )
    assert dirty["verdict"] == "FAIL"


def test_self_score_plant_ignores_model_fail_text():
    row = {
        "id": FLUENT_MISS_ID,
        "kind": "policy",
        "reference": {"fact": "30 days from delivery"},
    }
    result = {"answer": FLUENT_MISS_ANSWER, "planted_fluent_miss": True}
    scored = self_score(row, result, model=FakeChatModel(reply="FAIL"))
    assert scored["verdict"] == "PASS"
    assert scored["reason"] == "self-judge"
