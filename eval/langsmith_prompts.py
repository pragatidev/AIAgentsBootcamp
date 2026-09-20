"""Prompt Hub helpers and the local labels fallback for lab 9.2.3."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import ROOT
from dataflow.graphs.rag_graph import GENERATE_SYSTEM

PROMPT_NAME = "dataflow-system"
PROMPT_PATH = ROOT / "prompts" / "dataflow_system.md"
LABELS_PATH = ROOT / "eval" / "labels.jsonl"

REFUSAL_V1 = "say you do not have it."
REFUSAL_V2 = "say you do not have that in the knowledge base."


def prompt_v1() -> str:
    return GENERATE_SYSTEM


def prompt_v2() -> str:
    text = GENERATE_SYSTEM
    if REFUSAL_V1 in text:
        return text.replace(REFUSAL_V1, REFUSAL_V2, 1)
    return text + " If the passages do not contain the answer, " + REFUSAL_V2


def write_local_prompt(text: str, path: Path | None = None) -> Path:
    dest = path or PROMPT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text.strip() + "\n", encoding="utf-8")
    return dest


def extract_prompt_text(obj: Any) -> str:
    """Pull a system string out of whatever pull_prompt returned."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    messages = getattr(obj, "messages", None)
    if messages:
        parts: list[str] = []
        for msg in messages:
            inner = getattr(msg, "prompt", msg)
            template = getattr(inner, "template", None)
            if template:
                parts.append(str(template))
                continue
            content = getattr(msg, "content", None)
            if content:
                parts.append(str(content))
        if parts:
            return "\n".join(parts)
    template = getattr(obj, "template", None)
    if template:
        return str(template)
    return str(obj)


def as_chat_prompt(text: str) -> Any:
    from langchain_core.prompts import ChatPromptTemplate

    return ChatPromptTemplate.from_messages([("system", text)])


def write_labels(rows: list[dict[str, Any]], path: Path | None = None) -> Path:
    dest = path or LABELS_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(row, ensure_ascii=True) for row in rows
    ]
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
