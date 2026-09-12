# Replace notebook boot cells so they work from viralLoom cwd or a student clone root.
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BOOT = '''from pathlib import Path
import sys

def _find_root():
    hints = [
        Path("data") / "udemy" / "courses" / "ai_agents_bootcamp" / "course_repo",
        Path("course_repo"),
    ]
    def ok(p: Path) -> bool:
        return (p / "config.py").is_file() or (p / "src" / "llm.py").is_file()
    cur = Path.cwd().resolve()
    for p in [cur, *cur.parents]:
        if ok(p):
            return p
        for h in hints:
            cand = p / h
            if ok(cand):
                return cand.resolve()
    raise FileNotFoundError("Open this notebook from the AIAgentsBootcamp folder, or set cwd to that repo.")

_ROOT = _find_root()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from src.llm import REPO_ROOT, get_agent, get_embeddings, get_llm
llm = get_llm()
'''


def cell_text(cell: dict) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


def main() -> None:
    n = 0
    for path in ROOT.rglob("*.ipynb"):
        if any(part in {".git", ".venv", ".ipynb_checkpoints"} for part in path.parts):
            continue
        nb = json.loads(path.read_text(encoding="utf-8"))
        ch = False
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            text = cell_text(cell)
            if "from src.paths import ensure_sys_path" in text:
                cell["source"] = [BOOT]
                cell["outputs"] = []
                ch = True
        if ch:
            path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print("boot", path.relative_to(ROOT).as_posix())
            n += 1
    print("boot_count", n)


if __name__ == "__main__":
    main()
