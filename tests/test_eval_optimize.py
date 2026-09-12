"""12.2.2 Evaluator-optimizer. Pytest stays green with no live model."""

from talentflow.graphs.eval_optimize import run_eval_optimize
from talentflow.graphs.score_resumes import load_resumes
from tests.fixtures.fake_model import FakeChatModel

LOW = {
    "names_the_candidate": 0.4,
    "names_the_role": 0.4,
    "cites_one_resume_skill": 0.4,
    "under_180_words": 1.0,
    "total": 0.5,
}
MID = {
    "names_the_candidate": 0.6,
    "names_the_role": 0.6,
    "cites_one_resume_skill": 0.6,
    "under_180_words": 1.0,
    "total": 0.7,
}
HIGH = {
    "names_the_candidate": 1.0,
    "names_the_role": 1.0,
    "cites_one_resume_skill": 1.0,
    "under_180_words": 1.0,
    "total": 0.95,
}


def _sarah():
    loaded = load_resumes()
    row = next(r for r in loaded["resumes"] if r["name"] == "Sarah Chen")
    return row["name"], row["text"], loaded["job"]


def test_loop_stops_at_bar():
    name, resume, job = _sarah()
    model = FakeChatModel(
        reply="Hi Sarah Chen, Software Engineer, Python on the resume.",
        structured={"Scores": [LOW, MID, HIGH]},
    )
    out = run_eval_optimize(name=name, resume=resume, job=job, model=model)
    assert out.get("attempts") == 3
    assert out.get("stop_reason") == "bar reached"


def test_loop_stops_at_cap():
    name, resume, job = _sarah()
    model = FakeChatModel(
        reply="Hi there, we liked your file.",
        structured={"Scores": LOW},
    )
    out = run_eval_optimize(name=name, resume=resume, job=job, model=model)
    assert out.get("attempts") == 3
    assert out.get("stop_reason") == "cap hit"
