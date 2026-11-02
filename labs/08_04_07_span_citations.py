# %%
"""Lab 25.7: cite the lines, not just the file.

What we build: you type the small function that turns a chunk's character offset in its file into the
first and last line it covers. Every chunk of a text file already records that offset, so the citation can
say "lines 160 to 168" and a reviewer opens the file there. Then the refund question runs on the
support-agent desk with span citations on, and you plant one sentence the passages do not support to see
the claims check flag it.

What you learn: 25.1's idea taken one step further. A file and a heading say where to look; lines say what
to read. Lines come from the loader and the chunker, never from the model, and a sentence that shares no
word with any passage the answer was allowed to use is flagged in code. That check is a reviewer's aid, not
a judge: Section 25.5's judge stays the semantic check.

What will be true on your screen: three guide chunks with your line numbers beside the chunker's and
lines_match True, the refund section's lines opened from the file, the reply with its Sources lines and its
Claims, and the planted sentence printed as UNSUPPORTED. Then python -m pytest tests/test_lab_08_04_07.py -q.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.rag.chunk import chunk_by_heading, chunk_recursive
from dataflow.rag.cite import format_claims, support_spans
from dataflow.rag.load import KB_DIR, load_knowledge_base


# %%
# TYPE THIS: line_span. The signature and docstring are given; you type the body.
# Its finished copy is line_span in dataflow/rag/chunk.py, which stamps every chunk of a text file.
def line_span(source_text: str, start: int, length: int) -> tuple[int, int]:
    """The 1-based first and last line of the text that starts at offset start and runs length characters."""
    line_start = source_text.count("\n", 0, start) + 1
    line_end = source_text.count("\n", 0, start + max(length, 1) - 1) + 1
    return line_start, line_end


# BREAK: count lines from 0. Delete both "+ 1" at the ends of the two count lines, run the lab and read
# lines_match, then python -m pytest tests/test_lab_08_04_07.py -q. git checkout -- labs/08_04_07_span_citations.py puts it back.

guide = KB_DIR / "customer_facing" / "troubleshooting_guide.txt"
guide_doc = load_knowledge_base(roots=(guide,))[0]
matches = []
for chunk in chunk_recursive([guide_doc], chunk_size=1000)[:3]:
    mine = line_span(guide_doc.page_content, chunk.metadata["start_index"], len(chunk.page_content))
    theirs = (chunk.metadata["line_start"], chunk.metadata["line_end"])
    matches.append(mine == theirs)
    print("guide_chunk start_index", chunk.metadata["start_index"], "yours", mine, "chunker", theirs)
print("lines_match", all(matches))


# %%
# The refund section, opened from the file at the lines its chunk records.
procedures = KB_DIR / "internal_operations" / "support_operations" / "customer_support_procedures.markdown"
refund = next(c for c in chunk_by_heading(load_knowledge_base(roots=(procedures,))) if c.metadata.get("h3") == "6.1 Authorization Levels")
first, last = refund.metadata["line_start"], refund.metadata["line_end"]
print("refund_chunk_lines", first, "to", last)
lines = procedures.read_text(encoding="utf-8").split("\n")
for number in range(first, last + 1):
    print(f"{number:4d} | {lines[number - 1]}")


# %%
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("desk support_agent scope all, span_citations on")
state = build_rag_graph(model=chat, scope="all", span_citations=True).invoke({"question": "Who can approve a refund under 30 days?"})
print(state.get("reply"))


# %%
# Plant one sentence no passage supports, and run the claims check on the answer with it.
PLANTED = "Every desk lamp has a lifetime warranty."
kept = list(state.get("graded") or state.get("passages") or [])
claims = support_spans(str(state.get("answer") or "") + " " + PLANTED, kept)
print("Claims:")
print(format_claims(claims))
print("planted_flagged", any(claim["unsupported"] and claim["sentence"] == PLANTED for claim in claims))
