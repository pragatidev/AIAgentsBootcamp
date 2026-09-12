"""10.2 eval CI gate and judge parse. No Ollama required."""

from pathlib import Path

from eval.judges.llm_judge import parse_verdict
from tests.fixtures.fake_model import FakeChatModel

ROOT = Path(__file__).resolve().parents[1]


def _load_eval_ci():
    import importlib.util

    path = ROOT / "scripts" / "eval_ci.py"
    spec = importlib.util.spec_from_file_location("eval_ci", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_eval_ci_fixture_exits_0_on_baseline():
    mod = _load_eval_ci()
    code = mod.main(["--fixture"])
    assert code == 0


def test_eval_ci_impossible_floor_exits_1(tmp_path):
    bad = tmp_path / "impossible.toml"
    bad.write_text(
        "\n".join(
            [
                "[tracked]",
                "faithfulness = 1.5",
                "context_recall = 0.0",
                "refused_correctly = 0.0",
                "",
                "[tracked.max_drop]",
                "faithfulness = 1.0",
                "context_recall = 1.0",
                "refused_correctly = 1.0",
                "",
                "[reported]",
                "latency = true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    mod = _load_eval_ci()
    code = mod.main(["--fixture", "--thresholds", str(bad)])
    assert code == 1


def test_judge_parses_a_fixture_verdict():
    assert parse_verdict("grounded") == "grounded"
    assert parse_verdict("The verdict is UNGROUNDED.") == "ungrounded"
    assert parse_verdict("REFUSE") == "refuse"
    assert parse_verdict("park") == "park"
    model = FakeChatModel(reply="grounded")
    from eval.judges.llm_judge import judge_sample

    label = judge_sample(
        {"answer": "The customer return window is 30 days.", "passages": []},
        model=model,
    )
    assert label == "grounded"
