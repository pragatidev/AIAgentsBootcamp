"""TalentFlow evaluator-optimizer. Score a draft against a rubric until the bar or the cap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext
from talentflow.graphs.critic import writer

__all__ = [
    "EvalState",
    "RUBRIC_PATH",
    "Scores",
    "build_eval_optimize",
    "evaluator",
    "load_rubric",
    "run_eval_optimize",
]

TALENTFLOW = Path(__file__).resolve().parents[1]
RUBRIC_PATH = TALENTFLOW / "evals" / "email_rubric.json"

EVAL_SYSTEM = (
    "You score a TalentFlow outreach mail against a rubric. "
    "Each criterion is a number from 0 to 1. "
    "total is the weighted sum using the weights in the rubric. "
    "Score only what the draft actually says."
)


class EvalState(TypedDict, total=False):
    name: str
    resume: str
    job: str
    draft: str
    revision: str
    scores: dict[str, Any]
    attempts: int
    stop_reason: str
    history: list
    no_cap: bool
    cap: int
    bar: float


class Scores(BaseModel):
    names_the_candidate: float = Field(description="0 to 1, mail names the candidate")
    names_the_role: float = Field(description="0 to 1, mail names the role")
    cites_one_resume_skill: float = Field(
        description="0 to 1, mail cites one resume skill"
    )
    under_180_words: float = Field(description="0 to 1, mail is under 180 words")
    total: float = Field(description="Weighted sum of the four scores")


def load_rubric(path: Path | None = None) -> dict[str, Any]:
    target = path or RUBRIC_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def _resolve_chat(
    runtime: Runtime[DeskContext] | None,
    model: Any,
) -> Any:
    chat = model
    if chat is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        chat = getattr(ctx, "model", None) if ctx is not None else None
    if chat is None:
        chat = get_chat_model()
    return chat


def _scores_payload(decision: Any) -> dict[str, Any]:
    if decision is None:
        return {
            "names_the_candidate": 0.0,
            "names_the_role": 0.0,
            "cites_one_resume_skill": 0.0,
            "under_180_words": 0.0,
            "total": 0.0,
        }
    if hasattr(decision, "model_dump"):
        return decision.model_dump()
    if isinstance(decision, dict):
        return {
            "names_the_candidate": float(decision.get("names_the_candidate") or 0),
            "names_the_role": float(decision.get("names_the_role") or 0),
            "cites_one_resume_skill": float(
                decision.get("cites_one_resume_skill") or 0
            ),
            "under_180_words": float(decision.get("under_180_words") or 0),
            "total": float(decision.get("total") or 0),
        }
    return {
        "names_the_candidate": float(getattr(decision, "names_the_candidate", 0) or 0),
        "names_the_role": float(getattr(decision, "names_the_role", 0) or 0),
        "cites_one_resume_skill": float(
            getattr(decision, "cites_one_resume_skill", 0) or 0
        ),
        "under_180_words": float(getattr(decision, "under_180_words", 0) or 0),
        "total": float(getattr(decision, "total", 0) or 0),
    }


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def evaluator(state, runtime=None, *, model=None, rubric: dict[str, Any] | None = None):
    """Score the draft. Set stop_reason when the bar is reached or the cap hits."""
    chat = _resolve_chat(runtime, model)
    spec = rubric if rubric is not None else load_rubric()
    bar = float(state.get("bar") if state.get("bar") is not None else spec["bar"])
    cap = int(state.get("cap") if state.get("cap") is not None else spec["cap"])
    no_cap = bool(state.get("no_cap"))
    draft = str(state.get("draft") or "")
    structured = chat.with_structured_output(Scores)
    decision = structured.invoke(
        [
            {"role": "system", "content": EVAL_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Rubric:\n"
                    + json.dumps(spec, indent=2)
                    + "\n\nDraft:\n"
                    + draft
                ),
            },
        ]
    )
    scores = _scores_payload(decision)
    attempts = int(state.get("attempts") or 0) + 1
    history = list(state.get("history") or [])
    history.append(
        {
            "attempt": attempts,
            "scores": scores,
            "first_line": _first_line(draft),
        }
    )
    total = float(scores.get("total") or 0)
    stop = ""
    if total >= bar:
        stop = "bar reached"
    elif attempts >= cap:
        # Planted no-cap path uses a hard ceiling as cap; that is a cut, not the rubric cap.
        stop = "cut at " + str(attempts) if no_cap else "cap hit"
    update: dict[str, Any] = {
        "scores": scores,
        "attempts": attempts,
        "history": history,
        "revision": draft,
    }
    if stop:
        update["stop_reason"] = stop
    return update


def _after_evaluator(state: EvalState) -> str:
    if state.get("stop_reason"):
        return END
    return "writer"


def build_eval_optimize(
    model=None,
    no_cap: bool = False,
    hard_ceiling: int | None = None,
    rubric: dict[str, Any] | None = None,
):
    spec = rubric if rubric is not None else load_rubric()
    bar = float(spec["bar"])
    if no_cap:
        # Planted miss for the lab: no rubric cap. A hard ceiling still kills a runaway.
        cap = int(hard_ceiling) if hard_ceiling is not None else 32
    else:
        cap = int(spec["cap"])

    def writer_node(
        state: EvalState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return writer(state, runtime=runtime, model=model)

    def evaluator_node(
        state: EvalState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return evaluator(state, runtime=runtime, model=model, rubric=spec)

    def seed(state: EvalState) -> dict[str, Any]:
        return {
            "bar": bar,
            "cap": cap,
            "no_cap": bool(no_cap),
            "attempts": int(state.get("attempts") or 0),
            "history": list(state.get("history") or []),
        }

    builder = StateGraph(EvalState, context_schema=DeskContext)
    builder.add_node("seed", seed)
    builder.add_node("writer", writer_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "writer")
    builder.add_edge("writer", "evaluator")
    builder.add_conditional_edges("evaluator", _after_evaluator)
    return builder.compile()


def run_eval_optimize(
    *,
    name: str,
    resume: str,
    job: str,
    model: Any = None,
    no_cap: bool = False,
    hard_ceiling: int | None = None,
    rubric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph = build_eval_optimize(
        model=model,
        no_cap=no_cap,
        hard_ceiling=hard_ceiling,
        rubric=rubric,
    )
    return graph.invoke(
        {"name": name, "resume": resume, "job": job},
        {"recursion_limit": 80},
    )
