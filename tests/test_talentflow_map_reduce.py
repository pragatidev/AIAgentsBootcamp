"""6.7 TalentFlow map-reduce. Pytest stays green with no live model."""

from langgraph.types import Send

from talentflow.graphs.score_resumes import (
    RESUMES_DIR,
    build_score_resumes,
    fan_out,
    load_resumes,
)
from tests.fixtures.fake_model import FakeChatModel


def _thread(name: str) -> dict:
    return {"configurable": {"thread_id": name}}


def _resume_names() -> set[str]:
    names = set()
    prefix = "Resume - "
    for path in RESUMES_DIR.glob("*.markdown"):
        stem = path.stem
        names.add(stem[len(prefix) :] if stem.startswith(prefix) else stem)
    return names


def test_fan_out_sends_one_per_resume():
    loaded = load_resumes()
    sends = fan_out(loaded)
    names = [row["name"] for row in loaded["resumes"]]
    assert len(sends) == len(names)
    assert len(sends) == 10
    assert all(isinstance(item, Send) for item in sends)
    assert {item.node for item in sends} == {"score"}
    packed = {item.arg["name"] for item in sends}
    assert packed == set(names)


def test_map_reduce_scores_all():
    model = FakeChatModel(
        reply="Alex Thompson and Sarah Chen are the top two. The rest are possible. Hire from the top of the table.",
        structured={
            "ResumeScore": {
                "score": 80,
                "fit": "strong",
                "reason": "fixture score",
            }
        },
    )
    graph = build_score_resumes(model=model, limit=None)
    cfg = _thread("test-13-4-all")
    out = graph.invoke({}, cfg)
    scores = list(out.get("scores") or [])
    assert len(scores) == 10
    expected = _resume_names()
    assert {row["name"] for row in scores} == expected
    assert all(int(row["score"]) == 80 for row in scores)
    found_ten = False
    for snap in graph.get_state_history(cfg):
        score_next = [n for n in (snap.next or ()) if n == "score"]
        score_tasks = [t.name for t in (snap.tasks or ()) if t.name == "score"]
        if len(score_next) == 10 or len(score_tasks) == 10:
            found_ten = True
            break
    assert found_ten
