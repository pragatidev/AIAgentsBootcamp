"""TalentFlow map-reduce: one Send per resume, one ranking.

load reads the job and the pile. fan_out returns one Send per resume.
score sees only its packed state. summarize joins the scores.
"""

from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Send
from pydantic import BaseModel, Field

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext

__all__ = [
    "ParentState",
    "ResumeScore",
    "ScoreInput",
    "build_score_resumes",
    "fan_out",
    "load_resumes",
    "score",
    "summarize",
]

TALENTFLOW = Path(__file__).resolve().parents[1]
JOB_PATH = TALENTFLOW / "data" / "job_description.markdown"
RESUMES_DIR = TALENTFLOW / "data" / "resumes"

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


class ParentState(TypedDict, total=False):
    job: str
    resumes: list[dict]
    scores: Annotated[list, operator.add]
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


def _resume_name(path: Path) -> str:
    stem = path.stem
    prefix = "Resume - "
    if stem.startswith(prefix):
        return stem[len(prefix) :]
    return stem


def load_resumes(limit: int | None = None) -> dict[str, Any]:
    """Read the job description and the resume files. limit caps the pile."""
    job = JOB_PATH.read_text(encoding="utf-8")
    files = sorted(RESUMES_DIR.glob("*.markdown"))
    if limit is not None:
        files = files[: int(limit)]
    resumes = []
    for path in files:
        resumes.append(
            {
                "name": _resume_name(path),
                "text": path.read_text(encoding="utf-8"),
            }
        )
    return {"job": job, "resumes": resumes}


def fan_out(state: ParentState) -> list[Send]:
    """One Send per resume. Each copy gets its own small state."""
    job = str(state.get("job") or "")
    return [
        Send("score", {"name": r["name"], "text": r["text"], "job": job})
        for r in (state.get("resumes") or [])
    ]


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


def score(state: ScoreInput) -> dict:
    """Score one resume. Packed state only. Returns a one item list."""
    chat = get_chat_model()
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
    """Sort scores, write a table, ask the model for three sentences."""
    chat = _resolve_chat(runtime, model)
    rows = list(state.get("scores") or [])
    rows = sorted(rows, key=lambda r: (-int(r.get("score") or 0), str(r.get("name") or "")))
    lines = ["name\tscore\tfit"]
    for row in rows:
        lines.append(
            str(row.get("name") or "")
            + "\t"
            + str(row.get("score") or "")
            + "\t"
            + str(row.get("fit") or "")
        )
    table = "\n".join(lines)
    message = chat.invoke(
        [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": table},
        ]
    )
    summary = _content_text(message)
    ranking = table + "\n\n" + summary
    return {"ranking": ranking}


def build_score_resumes(checkpointer=None, model=None, limit=None):
    """Compile the map-reduce graph. limit caps how many resumes load reads."""
    if checkpointer is None:
        checkpointer = InMemorySaver()

    def load_node(state: ParentState) -> dict[str, Any]:
        return load_resumes(limit=limit)

    def score_node(state: ScoreInput) -> dict:
        chat = model
        if chat is None:
            return score(state)
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
