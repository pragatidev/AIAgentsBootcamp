"""Find the bootcamp repo whether cloned at root or nested under viralLoom."""

from __future__ import annotations

import os
from pathlib import Path

NESTED_HINTS = (
    Path("data") / "udemy" / "courses" / "ai_agents_bootcamp" / "course_repo",
    Path("course_repo"),
)


def _is_repo_root(path: Path) -> bool:
    if (path / "config.py").is_file() and (path / "dataflow").is_dir():
        return True
    src = path / "src"
    if src.is_dir() and (src / "llm.py").is_file():
        return True
    return False


def find_repo_root(*hints: Path | str) -> Path:
    """Walk up from cwd / hints. Also check the viralLoom nested layout.

    Student clone: AIAgentsBootcamp/ is the root.
    This workspace: .../viralLoom/data/udemy/courses/ai_agents_bootcamp/course_repo/
    Opening a notebook inside labs/ still walks up to that root.
    """
    starts: list[Path] = []
    env = os.environ.get("BOOTCAMP_ROOT", "").strip()
    if env:
        starts.append(Path(env))
    for h in hints:
        if h:
            starts.append(Path(h))
    starts.append(Path.cwd())

    seen: set[Path] = set()
    for start in starts:
        cur = start.expanduser().resolve()
        if cur.is_file():
            cur = cur.parent
        for p in [cur, *cur.parents]:
            if p in seen:
                continue
            seen.add(p)
            if _is_repo_root(p):
                return p
            for hint in NESTED_HINTS:
                cand = p / hint
                if _is_repo_root(cand):
                    return cand.resolve()
    raise FileNotFoundError(
        "Cannot find the AI Agents Bootcamp repo. "
        "Open the notebook from the cloned repo folder, or set BOOTCAMP_ROOT."
    )


def load_dotenv(root: Path | None = None) -> Path | None:
    """Load .env from the repo root. Never print values."""
    root = root or find_repo_root()
    env_path = root / ".env"
    if not env_path.is_file():
        return None
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return env_path


def ensure_sys_path(root: Path | None = None) -> Path:
    import sys

    root = root or find_repo_root()
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)
    return root
