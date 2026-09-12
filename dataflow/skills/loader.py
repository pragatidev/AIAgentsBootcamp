"""Load DataFlow SKILL.md folders: L1 frontmatter, L2 body, L3 references."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from config import get_chat_model

ROOT = Path(__file__).resolve().parent
SKILLS_ROOT = ROOT
TOKEN_METHOD = "tiktoken cl100k_base after get_num_tokens fails or is missing"


class SkillPick(BaseModel):
    name: str = Field(
        description="The matching skill name, or none if no skill applies"
    )


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from the body. Tiny parser, no extra package."""
    raw = text.replace("\r\n", "\n")
    if not raw.startswith("---"):
        return {}, raw.strip("\n") + ("\n" if raw.strip() else "")
    rest = raw[3:].lstrip("\n")
    end = rest.find("\n---")
    if end < 0:
        return {}, raw
    yaml_text = rest[:end]
    body = rest[end + 4 :].lstrip("\n")
    meta: dict[str, Any] = {}
    current: str | None = None
    for line in yaml_text.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current:
            value = line[4:].strip().strip('"').strip("'")
            existing = meta.get(current)
            if not isinstance(existing, list):
                meta[current] = []
            meta[current].append(value)
            continue
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            current = key.strip()
            value = value.strip()
            if value == "":
                meta[current] = []
            else:
                meta[current] = value.strip('"').strip("'")
    return meta, body


def load_skills(root: str | Path | None = None) -> list[dict[str, Any]]:
    """L1: read every SKILL.md frontmatter under root."""
    base = Path(root) if root is not None else SKILLS_ROOT
    skills: list[dict[str, Any]] = []
    for path in sorted(base.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        skill = dict(meta)
        skill["path"] = path
        skill["folder"] = path.parent
        skill["body"] = body
        skill["frontmatter"] = meta
        skills.append(skill)
    return skills


def load_body(skill: dict[str, Any]) -> str:
    """L2: the SKILL.md body."""
    return str(skill.get("body") or "")


def load_reference(skill: dict[str, Any], name: str) -> str:
    """L3: a file from the skill's references folder."""
    folder = Path(skill["folder"])
    path = folder / "references" / name
    return path.read_text(encoding="utf-8")


def count_tokens(text: str, model: Any = None) -> int:
    """Count tokens. Prefer the model's get_num_tokens, else tiktoken.

    ChatOllama.get_num_tokens exists but raises ImportError without
    transformers. We catch that and use tiktoken cl100k_base. If tiktoken
    is missing, we count whitespace-separated words.
    """
    chat = model
    if chat is not None and hasattr(chat, "get_num_tokens"):
        try:
            return int(chat.get_num_tokens(text))
        except Exception:
            pass
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text or ""))
    except Exception:
        words = (text or "").split()
        return len(words)


def match(ticket: str, skills: list[dict[str, Any]], model: Any = None) -> dict[str, Any] | None:
    """Ask the model which skill description matches. Structured, or none."""
    chat = model if model is not None else get_chat_model()
    lines = []
    for skill in skills:
        lines.append(
            str(skill.get("name") or "")
            + ": "
            + str(skill.get("description") or "")
        )
    catalog = "\n".join(lines) if lines else "(none)"
    structured = chat.with_structured_output(SkillPick)
    pick = structured.invoke(
        [
            {
                "role": "system",
                "content": (
                    "Pick the skill whose description matches the ticket. "
                    "Reply with the skill name, or none if no skill applies."
                ),
            },
            {
                "role": "user",
                "content": "Skills:\n" + catalog + "\n\nTicket:\n" + ticket,
            },
        ]
    )
    name = ""
    if hasattr(pick, "name"):
        name = str(pick.name or "")
    elif isinstance(pick, dict):
        name = str(pick.get("name") or "")
    else:
        name = str(pick)
    cleaned = name.strip().strip('"').strip("'")
    if not cleaned or cleaned.lower() == "none":
        return None
    for skill in skills:
        if str(skill.get("name") or "") == cleaned:
            return skill
    return None
