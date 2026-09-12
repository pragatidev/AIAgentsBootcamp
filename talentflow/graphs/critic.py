"""TalentFlow critic. Writer drafts, critic returns misses, writer revises once."""

from __future__ import annotations

import os
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext

__all__ = [
    "CRITIC_FACTS",
    "CriticState",
    "Miss",
    "Misses",
    "build_critic",
    "critic",
    "writer",
]

SKILL_NEEDLES = (
    "Python",
    "JavaScript",
    "TypeScript",
    "React",
    "Node.js",
    "PostgreSQL",
    "Django",
    "FastAPI",
    "AWS",
    "Docker",
)

CRITIC_FACTS = (
    "the candidate's name",
    "one skill from the resume",
    "the role title from the job file",
)

WRITER_SYSTEM = (
    "You write one TalentFlow outreach mail. "
    "Name the candidate, name the role title from the job file, "
    "and cite one skill from the resume. "
    "Keep it under 180 words. Plain text. No subject line required."
)

REVISE_SYSTEM = (
    "You revise a TalentFlow outreach mail. "
    "Fix every miss in the list. Keep the rest. "
    "Name the candidate, name the role, cite one resume skill. "
    "Keep it under 180 words. Plain text."
)

CRITIC_SYSTEM = (
    "You are the TalentFlow critic. "
    "Compare the draft against the resume and the job file. "
    "You must check three facts: the candidate's name, one skill from "
    "the resume, the role title from the job file. "
    "Return a miss for each fact the draft is missing or has wrong. "
    "what is the fact. where is resume or job file. "
    "If the draft has all three, return an empty list."
)


class CriticState(TypedDict, total=False):
    name: str
    resume: str
    job: str
    draft: str
    misses: list
    revision: str


class Miss(BaseModel):
    what: str = Field(description="The fact that is missing or wrong")
    where: str = Field(description="resume or job file")


class Misses(BaseModel):
    items: list[Miss] = Field(description="Misses the draft still has")


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


def _plant_empty(flag: bool) -> bool:
    if flag:
        return True
    raw = os.environ.get("TALENTFLOW_PLANT_EMPTY_CRITIC", "").strip().lower()
    return raw in {"1", "true", "yes"}


def role_title(job: str) -> str:
    for line in (job or "").splitlines():
        text = line.strip()
        if text.startswith("#"):
            title = text.lstrip("#").strip()
            if " - " in title:
                return title.split(" - ", 1)[0].strip()
            return title
    return "Software Engineer"


def pick_skill(resume: str) -> str:
    blob = resume or ""
    for skill in SKILL_NEEDLES:
        if skill.lower() in blob.lower():
            return skill
    return "Python"


def _code_misses(draft: str, name: str, resume: str, job: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    body = draft or ""
    lowered = body.lower()
    if name and name.lower() not in lowered:
        items.append({"what": "candidate name " + name, "where": "resume"})
    skill = pick_skill(resume)
    if skill.lower() not in lowered:
        items.append({"what": "skill " + skill, "where": "resume"})
    role = role_title(job)
    if role.lower() not in lowered:
        items.append({"what": "role title " + role, "where": "job file"})
    return items


def _items_of(decision: Any) -> list[dict[str, str]]:
    if decision is None:
        return []
    if hasattr(decision, "items"):
        raw = decision.items
    elif isinstance(decision, dict):
        raw = decision.get("items") or []
    else:
        raw = []
    out: list[dict[str, str]] = []
    for item in raw or []:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if isinstance(item, dict):
            what = str(item.get("what") or "").strip()
            where = str(item.get("where") or "").strip()
            if what:
                out.append({"what": what, "where": where})
    return out


def _merge_misses(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for group in groups:
        for item in group:
            key = (item.get("what") or "").lower() + "|" + (item.get("where") or "").lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out


def writer(state, runtime=None, *, model=None):
    """Draft, or revise when misses or scores are already on state."""
    chat = _resolve_chat(runtime, model)
    name = str(state.get("name") or "")
    resume = str(state.get("resume") or "")
    job = str(state.get("job") or "")
    draft = str(state.get("draft") or "")
    misses = state.get("misses")
    scores = state.get("scores")
    sources = (
        "Candidate: "
        + name
        + "\n\nJob description:\n"
        + job
        + "\n\nResume:\n"
        + resume
    )
    if scores:
        message = chat.invoke(
            [
                {"role": "system", "content": REVISE_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        sources
                        + "\n\nDraft:\n"
                        + draft
                        + "\n\nScores:\n"
                        + str(scores)
                    ),
                },
            ]
        )
        text = _content_text(message).strip()
        return {"draft": text, "revision": text}
    if misses is not None:
        if not misses:
            return {"revision": draft}
        message = chat.invoke(
            [
                {"role": "system", "content": REVISE_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        sources
                        + "\n\nDraft:\n"
                        + draft
                        + "\n\nMisses:\n"
                        + str(misses)
                    ),
                },
            ]
        )
        return {"revision": _content_text(message).strip()}
    message = chat.invoke(
        [
            {"role": "system", "content": WRITER_SYSTEM},
            {"role": "user", "content": sources},
        ]
    )
    return {"draft": _content_text(message).strip()}


def critic(state, runtime=None, *, model=None, plant_empty: bool = False):
    """Return a structured miss list. Planted path always returns empty."""
    if _plant_empty(plant_empty):
        # Planted miss for the lab: the critic always returns an empty list.
        return {"misses": []}
    chat = _resolve_chat(runtime, model)
    structured = chat.with_structured_output(Misses)
    name = str(state.get("name") or "")
    resume = str(state.get("resume") or "")
    job = str(state.get("job") or "")
    draft = str(state.get("draft") or "")
    decision = structured.invoke(
        [
            {"role": "system", "content": CRITIC_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Candidate: "
                    + name
                    + "\n\nJob description:\n"
                    + job
                    + "\n\nResume:\n"
                    + resume
                    + "\n\nDraft:\n"
                    + draft
                    + "\n\nCheck these three facts: "
                    + ", ".join(CRITIC_FACTS)
                    + "."
                ),
            },
        ]
    )
    coded = _code_misses(draft, name, resume, job)
    merged = _merge_misses(coded, _items_of(decision))
    return {"misses": merged}


def build_critic(model=None, plant_empty: bool = False):
    builder = StateGraph(CriticState, context_schema=DeskContext)

    def writer_node(
        state: CriticState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return writer(state, runtime=runtime, model=model)

    def critic_node(
        state: CriticState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return critic(
            state,
            runtime=runtime,
            model=model,
            plant_empty=plant_empty,
        )

    def after_writer(state: CriticState) -> str:
        if state.get("misses") is None:
            return "critic"
        return END

    builder.add_node("writer", writer_node)
    builder.add_node("critic", critic_node)
    builder.add_edge(START, "writer")
    builder.add_conditional_edges("writer", after_writer)
    builder.add_edge("critic", "writer")
    return builder.compile()
