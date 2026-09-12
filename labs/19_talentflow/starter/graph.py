"""TalentFlow map-reduce starter. The scores key has no reducer on purpose."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Send
from pydantic import BaseModel, Field

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext

FILL_FROM_REPO = False  # TODO fill: import and delegate from the finished package


class ParentState(TypedDict, total=False):
    job: str
    resumes: list[dict]
    scores: list  # TODO reducer: Annotated[list, operator.add]
    ranking: str


class ScoreInput(TypedDict):
    name: str
    text: str
    job: str


class ResumeScore(BaseModel):
    score: int = Field(description="Integer from 0 to 100")
    fit: Literal["strong", "possible", "no"] = Field(
        description="strong, possible, or no"
    )
    reason: str = Field(description="One sentence")


SCORE_SYSTEM = (
    "You score one resume against one job description. "
    "score is an integer from 0 to 100. "
    "fit is strong, possible, or no. "
    "reason is one sentence. "
    "Do not mention other candidates."
)

SUMMARY_SYSTEM = (
    "You write a TalentFlow ranking summary. "
    "Write exactly three sentences. "
    "Name the top two candidates by the scores in the table. "
    "Do not invent a score that is not in the table."
)


def template_paths() -> list[str]:
    from pathlib import Path

    for item in list(__import__("sys").path):
        folder = Path(item) / "talentflow" / "data" / "templates"
        if folder.is_dir():
            return sorted(p.as_posix() for p in folder.glob("*.markdown"))
    return []


def load_resumes(limit: int | None = None) -> dict[str, Any]:
    """TODO load: read the job description and the resume files."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("read the job description and the resume files")
    from talentflow.graphs.score_resumes import load_resumes as _load

    return _load(limit=limit)


def fan_out(state: ParentState) -> list[Send]:
    """Wired. One Send per resume."""
    job = str(state.get("job") or "")
    return [
        Send("score", {"name": r["name"], "text": r["text"], "job": job})
        for r in (state.get("resumes") or [])
    ]


def _content_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(p for p in parts if p)
    if content is None:
        return ""
    return str(content)


def score(state: ScoreInput, model: Any = None) -> dict:
    """TODO score: score one resume with the model from config."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("score one resume with the model from config")
    chat = model or get_chat_model()
    structured = chat.with_structured_output(ResumeScore)
    name = str(state.get("name") or "")
    text = str(state.get("text") or "")
    job = str(state.get("job") or "")
    decision = structured.invoke(
        [
            {"role": "system", "content": SCORE_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Candidate: "
                    + name
                    + "\n\nJob description:\n"
                    + job
                    + "\n\nResume:\n"
                    + text
                ),
            },
        ]
    )
    if hasattr(decision, "score"):
        payload = {
            "name": name,
            "score": int(decision.score),
            "fit": str(decision.fit),
            "reason": str(decision.reason),
        }
    else:
        payload = {
            "name": name,
            "score": int(decision["score"]),
            "fit": str(decision["fit"]),
            "reason": str(decision["reason"]),
        }
    return {"scores": [payload]}


def summarize(
    state: ParentState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, str]:
    """TODO summarize: join the scores and ask the model for three sentences."""
    if not FILL_FROM_REPO:
        raise NotImplementedError(
            "join the scores and ask the model for three sentences"
        )
    from talentflow.graphs.score_resumes import summarize as _sum

    return _sum(state, runtime=runtime, model=model)


def build_pipeline(checkpointer=None, model=None, limit=None):
    if checkpointer is None:
        checkpointer = InMemorySaver()

    def load_node(state: ParentState) -> dict[str, Any]:
        return load_resumes(limit=limit)

    def score_node(state: ScoreInput) -> dict:
        return score(state, model=model)

    def summarize_node(
        state: ParentState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return summarize(state, runtime=runtime, model=model)

    builder = StateGraph(ParentState, context_schema=DeskContext)
    builder.add_node("load", load_node)
    builder.add_node("score", score_node)
    builder.add_node("summarize", summarize_node)
    builder.add_edge(START, "load")
    builder.add_conditional_edges("load", fan_out, ["score"])
    builder.add_edge("score", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile(checkpointer=checkpointer)


# Silence unused import when the student has not added the reducer yet.
_ = (operator, Annotated)
