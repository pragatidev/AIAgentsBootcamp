"""TalentFlow graphs. Map-reduce over the resume pile lives here."""

from talentflow.graphs.score_resumes import build_score_resumes, fan_out, load_resumes
from talentflow.graphs.critic import build_critic, critic
from talentflow.graphs.eval_optimize import build_eval_optimize

__all__ = [
    "build_score_resumes",
    "fan_out",
    "load_resumes",
    "build_critic",
    "critic",
    "build_eval_optimize",
]

