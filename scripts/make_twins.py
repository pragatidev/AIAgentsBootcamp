"""Convert labs/*.py with # %% cells into labs/*.ipynb twins. Idempotent."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "labs"


def split_cells(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    cells: list[tuple[str, str]] = []
    current_type = "code"
    current: list[str] = []
    seen_marker = False

    def flush() -> None:
        source = "\n".join(current).strip("\n")
        cells.append((current_type, source))

    for line in lines:
        if line.startswith("# %%"):
            if seen_marker or current:
                flush()
            seen_marker = True
            rest = line[4:].strip()
            if rest.startswith("[markdown]"):
                current_type = "markdown"
            else:
                current_type = "code"
            current = []
            continue
        if not seen_marker:
            seen_marker = True
            current_type = "code"
        current.append(line)
    if seen_marker or current:
        flush()
    return [(kind, src) for kind, src in cells if src.strip() or kind == "code"]


def markdown_source(raw: str) -> str:
    out: list[str] = []
    for line in raw.splitlines():
        if line.startswith("# "):
            out.append(line[2:])
        elif line == "#":
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def as_source_list(text: str) -> list[str]:
    if not text:
        return []
    if not text.endswith("\n"):
        text = text + "\n"
    return [text]


def build_notebook(cells: list[tuple[str, str]]) -> dict:
    nb_cells = []
    for kind, source in cells:
        if kind == "markdown":
            nb_cells.append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": as_source_list(markdown_source(source)),
                }
            )
        else:
            nb_cells.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": as_source_list(source),
                }
            )
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "cells": nb_cells,
    }


def convert_file(py_path: Path) -> Path | None:
    text = py_path.read_text(encoding="utf-8")
    if "# %%" not in text:
        return None
    cells = split_cells(text)
    nb = build_notebook(cells)
    out = py_path.with_suffix(".ipynb")
    payload = json.dumps(nb, indent=1, ensure_ascii=True) + "\n"
    if out.is_file() and out.read_text(encoding="utf-8") == payload:
        print("unchanged", out.relative_to(ROOT).as_posix())
        return out
    out.write_text(payload, encoding="utf-8")
    print("wrote", out.relative_to(ROOT).as_posix(), "cells", len(cells))
    return out


def main() -> int:
    written = 0
    for py_path in sorted(LABS.glob("*.py")):
        if convert_file(py_path) is not None:
            written += 1
    print("twins", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
