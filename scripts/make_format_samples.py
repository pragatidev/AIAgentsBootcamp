"""Render one customer-facing markdown page as a PDF and a Word file for lab 22.6. Maintainer script.

The two files under dataflow/documents/ are committed, so a student needs only the readers (pypdf and
python-docx); this script needs reportlab and python-docx and is run by a maintainer when the page
changes. No fact is added: every line of the two files is a line of the markdown with its markup
removed (bold, code ticks and link targets). Headings become Word heading styles and PDF bookmarks,
the way an office export carries them. Run: python scripts/make_format_samples.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dataflow" / "knowledge_base" / "customer_facing" / "product_user_guide.markdown"
OUT_DIR = ROOT / "dataflow" / "documents"

_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def plain(line: str) -> str:
    """A markdown line as the words a reader shows: no bold stars, no code ticks, a link as its text and target."""
    line = _LINK.sub(r"\1 (\2)", line)
    return line.replace("**", "").replace("`", "").strip()


def blocks(text: str) -> list[tuple[str, int, str]]:
    """The page as (kind, level, text): kind is heading (level 1 to 3) or line. Rules and blank lines are dropped."""
    out: list[tuple[str, int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.strip() == "---":
            continue
        match = _HEADING.match(raw)
        if match:
            out.append(("heading", len(match.group(1)), plain(match.group(2))))
        else:
            out.append(("line", 0, plain(raw)))
    return out


def write_pdf(items: list[tuple[str, int, str]], path: Path) -> None:
    from reportlab import rl_config
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    from xml.sax.saxutils import escape

    rl_config.invariant = 1
    styles = getSampleStyleSheet()

    class Outlined(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            level = getattr(flowable, "_outline_level", None)
            if level is None:
                return
            key = f"h{self.heading_count}"
            self.heading_count += 1
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key, level=level - 1, closed=False)

    doc = Outlined(str(path), pagesize=A4, title="DataFlow Solutions User Guide", author="DataFlow Solutions")
    doc.heading_count = 0
    story = []
    for kind, level, text in items:
        if kind == "heading":
            para = Paragraph(escape(text), styles[f"Heading{level}"])
            para._outline_level = level
        else:
            para = Paragraph(escape(text), styles["BodyText"])
        story.append(para)
    doc.build(story)


def write_docx(items: list[tuple[str, int, str]], path: Path) -> None:
    import datetime

    from docx import Document

    doc = Document()
    for kind, level, text in items:
        if kind == "heading":
            doc.add_heading(text, level=level)
        else:
            doc.add_paragraph(text)
    fixed = datetime.datetime(2026, 11, 2, 0, 0, 0)
    doc.core_properties.created = fixed
    doc.core_properties.modified = fixed
    doc.core_properties.title = "DataFlow Solutions User Guide"
    doc.save(str(path))


def main() -> int:
    items = blocks(SOURCE.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_pdf(items, OUT_DIR / "product_user_guide.pdf")
    write_docx(items, OUT_DIR / "product_user_guide.docx")
    headings = sum(1 for kind, _, _ in items if kind == "heading")
    print("source", SOURCE.relative_to(ROOT).as_posix())
    print("blocks", len(items), "headings", headings)
    for name in ("product_user_guide.pdf", "product_user_guide.docx"):
        print("wrote", (OUT_DIR / name).relative_to(ROOT).as_posix(), (OUT_DIR / name).stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
