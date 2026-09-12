"""TalentFlow graphs. Map-reduce over the resume pile lives here."""

from talentflow.graphs.score_resumes import build_score_resumes, fan_out, load_resumes

__all__ = ["build_score_resumes", "fan_out", "load_resumes"]

