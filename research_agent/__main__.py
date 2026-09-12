"""python -m research_agent "question"

Runs the research agent with a real folder backend and prints the report path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from research_agent.agent import (
    PACKAGE_DIR,
    build_research_agent,
    find_report_files,
    make_real_backend,
    report_from_state,
)

RECURSION_LIMIT = 40


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DataFlow research and report agent")
    parser.add_argument("question", nargs="+", help="Research question")
    args = parser.parse_args(argv)
    question = " ".join(args.question)
    backend = make_real_backend()
    agent = build_research_agent(backend=backend)
    print("model", config.CHAT_MODEL)
    print("backend", type(backend).__name__)
    print("root", PACKAGE_DIR.as_posix())
    print("question", question)
    print("recursion_limit", RECURSION_LIMIT)
    payload = {"messages": [{"role": "user", "content": question}]}
    run_config = {"recursion_limit": RECURSION_LIMIT}
    result = None
    try:
        result = agent.invoke(payload, run_config)
    except Exception as exc:
        print("run_error", type(exc).__name__)
        print(str(exc))
    on_disk = find_report_files(PACKAGE_DIR)
    if on_disk:
        newest = max(on_disk, key=lambda p: p.stat().st_mtime)
        print("report_path", newest.as_posix())
        return 0
    if isinstance(result, dict):
        virtual_path, _text = report_from_state(result)
        if virtual_path:
            print("report_path", virtual_path)
            print("The report is in the virtual filesystem only.")
            return 0
        todos = result.get("todos")
        print("todos", todos)
    print("report_path", "none")
    print("The agent never wrote a report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
