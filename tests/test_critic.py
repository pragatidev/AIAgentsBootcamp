"""12.1.6 TalentFlow critic. Pytest stays green with no live model."""

from talentflow.graphs.critic import build_critic, critic
from talentflow.graphs.score_resumes import load_resumes
from tests.fixtures.fake_model import FakeChatModel

MISSING_ROLE_DRAFT = (
    "Hi Sarah Chen, your Python work stood out on the resume. "
    "I would like to set up a short call this week."
)
REVISED_WITH_ROLE = (
    "Hi Sarah Chen, your Python work fits the Software Engineer role "
    "at TechFlow Solutions. I would like to set up a short call this week."
)


def _sarah():
    loaded = load_resumes()
    row = next(r for r in loaded["resumes"] if r["name"] == "Sarah Chen")
    return row["name"], row["text"], loaded["job"]


def test_critic_flags_missing_role():
    name, resume, job = _sarah()
    out = critic(
        {
            "name": name,
            "resume": resume,
            "job": job,
            "draft": MISSING_ROLE_DRAFT,
        },
        model=FakeChatModel(structured={"Misses": {"items": []}}),
    )
    misses = list(out.get("misses") or [])
    assert len(misses) >= 1
    blob = " ".join(str(item.get("what") or "") for item in misses).lower()
    assert "role" in blob


def test_revision_contains_the_fact():
    name, resume, job = _sarah()
    model = FakeChatModel(
        reply=[MISSING_ROLE_DRAFT, REVISED_WITH_ROLE],
        structured={"Misses": {"items": []}},
    )
    graph = build_critic(model=model)
    out = graph.invoke({"name": name, "resume": resume, "job": job})
    revision = str(out.get("revision") or "")
    assert "Software Engineer" in revision
