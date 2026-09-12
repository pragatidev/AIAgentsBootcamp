"""Filled pipeline. Fixture model. scores has a reducer."""

from __future__ import annotations

from typing import Annotated, get_origin, get_type_hints

from graph import ParentState, build_pipeline, fan_out, load_resumes
from tests.fixtures.fake_model import FakeChatModel


def test_scores_key_has_reducer():
    ann = get_type_hints(ParentState, include_extras=True)["scores"]
    assert get_origin(ann) is Annotated


def test_fan_out_matches_load():
    loaded = load_resumes()
    sends = fan_out(loaded)
    assert len(sends) == len(loaded["resumes"])
    assert len(sends) == 10


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
    graph = build_pipeline(model=model, limit=None)
    out = graph.invoke({}, {"configurable": {"thread_id": "sol-all"}})
    scores = list(out.get("scores") or [])
    assert len(scores) == 10
    assert all(int(row["score"]) == 80 for row in scores)
    ranking = str(out.get("ranking") or "")
    assert "Alex Thompson" in ranking or "Sarah Chen" in ranking or "score" in ranking.lower()
