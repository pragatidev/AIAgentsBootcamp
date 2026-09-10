# Execute live lecture notebooks. Never print secrets.
from __future__ import annotations

import json
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_IF_CONTAINS = (
    "langflow run",
    "Run this in your terminal",
)

# Current live lectures that must actually run.
TARGETS = [
    "Section_2_Setup/Lecture_4_First_AI_Agent_Workflow.ipynb",
    "Section_3_LangChain_GPT4/Lecture_1_LangChain_Core_Components.ipynb",
    "Section_3_LangChain_GPT4/Lecture_2_Prompt_Engineering_GPT4.ipynb",
    "Section_3_LangChain_GPT4/Lecture_3_Adding_Memory_LangChain.ipynb",
    "Section_5_Autonomous_Workflows/Lecture_1_Task_Automation_Agents.ipynb",
    "Section_5_Autonomous_Workflows/Lecture_2_API_Custom_Tools.ipynb",
    "Section_6_Real_World_RAG_Engineering/Lecture_1_Custom_Tool_Integration.ipynb",
    "Section_6_Real_World_RAG_Engineering/Lecture_2_Intro_to_RAG_Modern.ipynb",
    "Section_7_Autogen_Multi_Agent_Systems/Lecture_2_Hands_on_with_AutoGen.ipynb",
]


def cell_text(cell: dict) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


def run_notebook(path: Path) -> tuple[str, str]:
    nb = json.loads(path.read_text(encoding="utf-8"))
    g: dict = {"__name__": "__main__"}
    for i, cell in enumerate(nb.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        src = cell_text(cell).strip()
        if not src:
            continue
        if any(s in src for s in SKIP_IF_CONTAINS):
            continue
        try:
            exec(compile(src, f"{path.name}:cell{i}", "exec"), g, g)
        except Exception as exc:
            return "FAIL", f"cell {i}: {type(exc).__name__}: {exc}"
    return "PASS", "ok"


def main() -> None:
    print("repo", ROOT)
    for rel in TARGETS:
        path = ROOT / rel
        print("BEGIN", rel)
        if not path.is_file():
            print("RESULT MISS")
            continue
        status, detail = run_notebook(path)
        print("RESULT", status, detail)
        if status == "FAIL":
            traceback.print_exc() if False else None
        print("END", rel)


if __name__ == "__main__":
    main()
