"""End a lab early and cleanly, as a script and as its notebook twin.

A script stops with exit code 0. A Jupyter kernel shows SystemExit as an error,
so inside a notebook the lab prints its line and the cells after this one run
as empty cells. Fix what the line asks for, restart the kernel, run it again.
Call it as the last line of a cell.
"""

from __future__ import annotations

import sys

FRAMEWORKS_LINE = (
    "This lab compares frameworks; install them once with: "
    "pip install -r requirements-frameworks.txt"
)
AUTOGEN_LINE = (
    "This lab compares frameworks; AutoGen clashes with the course install, "
    "so it gets its own venv: the steps are at the top of requirements-frameworks.txt"
)
CREWAI_LINE = (
    "This lab compares frameworks; CrewAI clashes with the course install, "
    "so it gets its own venv: the steps are at the top of requirements-frameworks.txt"
)


def _kernel():
    try:
        from IPython import get_ipython
    except ImportError:
        return None
    shell = get_ipython()
    if shell is None or type(shell).__name__ != "ZMQInteractiveShell":
        return None
    return shell


def quiet_exit(message: str | None = None) -> None:
    if message:
        print(message)
    shell = _kernel()
    if shell is None:
        sys.exit(0)
    if not getattr(shell, "_lab_quiet_exit", False):
        shell._lab_quiet_exit = True
        shell.input_transformers_cleanup.append(lambda lines: [])
        print("(the rest of this notebook is skipped; restart the kernel to run it again)")
