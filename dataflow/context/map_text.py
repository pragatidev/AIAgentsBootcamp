"""Fat instruction file and the map. Content lives on disk; the map is a table of contents."""

from __future__ import annotations

from pathlib import Path

KB = Path(__file__).resolve().parents[1] / "knowledge_base"
WIKI = Path(__file__).resolve().parents[1] / "wiki"
CONTEXT_DIR = Path(__file__).resolve().parent
MAP_PATH = CONTEXT_DIR / "MAP.md"

# The seed the repo ships in dataflow/context/MAP.md. Desks read the file, through load_map.
MAP = """You are the DataFlow support desk.
Role: answer customer tickets from this map.
Scope: customer-facing support only. Never quote HR or competitive analysis to a customer.
Tool rules: call read_file when the map says when. Call write_note when a fact must survive.
Refusal: if the map has no line for the question, say you do not have that.
Map:
return_policy.md | when the customer asks about returns or refunds
shipping.md | when the customer asks where an order is or about delivery windows
billing_and_pricing.csv | when the ticket is about charges, plans, or invoices
product_user_guide.markdown | when the customer asks how to use the product
troubleshooting_guide.txt | when something is not working
terms_of_service.markdown | when the customer asks about terms
api_documentation.json | when the ticket is about the API
customer_support_procedures.markdown | when you need a desk procedure
orders.json | when the ticket names an order id such as DF-1001
privacy_policy.txt | when the customer asks how their data is kept
employee_handbook.txt | when the ticket is from HR, never for a customer
competitive_analysis.txt | when a salesperson asks, never for a customer reply
security.md | when the customer asks about passwords or account security
"""

FAT_PREAMBLE = """You are the DataFlow support desk. Follow every policy below on every call.
Role: answer every ticket from the encyclopedia pasted here.
Scope: you have every document. Use them all.
Tool rules: you should not need tools because the files are already in this prompt.
Refusal: if the answer is not in the paste, say you do not have that.
Encyclopedia:
"""

FAT_RELATIVE = [
    WIKI / "return_policy.md",
    WIKI / "shipping.md",
    KB / "internal_operations" / "support_operations" / "customer_support_procedures.markdown",
    KB / "internal_operations" / "hr_policies" / "employee_handbook.txt",
    KB / "customer_facing" / "competitive_analysis.txt",
    KB / "legal_compliance" / "privacy_policy.txt",
]


def get_fat() -> str:
    parts = [FAT_PREAMBLE]
    for path in FAT_RELATIVE:
        parts.append("FILE " + path.name)
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


# The footer lines that say who owns the map. load_map leaves them out of what the desk sees.
HEADER_KEYS = ("owner", "reviewed", "version")


def _is_header(line: str) -> bool:
    return any(line.startswith(key + ":") for key in HEADER_KEYS)


def load_map(path: Path = MAP_PATH) -> str:
    """The map the desk runs on: the text of dataflow/context/MAP.md, as you wrote it, without its owner lines."""
    lines = [ln for ln in Path(path).read_text(encoding="utf-8").splitlines() if not _is_header(ln)]
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def map_header(path: Path = MAP_PATH) -> dict:
    """The owner, reviewed and version lines of MAP.md, as a dict."""
    header = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if _is_header(line):
            key, _, value = line.partition(":")
            header[key] = value.strip()
    return header


def check_map(text: str, require_owner: bool = False) -> list[str]:
    """One problem per map entry a desk could not use: no bar, no when, or a file read_file cannot open.

    require_owner also asks for an owner: line, which the raw file carries and load_map leaves out.
    """
    from dataflow.context.agent import _ALLOWED_NAMES

    problems = []
    if require_owner and not any(_is_header(ln) and ln.startswith("owner:") and ln[6:].strip() for ln in text.splitlines()):
        problems.append("MAP.md: no owner line")
    for line in text.split("Map:", 1)[-1].splitlines():
        if not line.strip() or _is_header(line):
            continue
        name, bar, when = line.partition(" | ")
        name = name.strip()
        if not bar or "when" not in when.lower():
            problems.append(line + ": needs a name, a bar and a when")
        elif name not in _ALLOWED_NAMES or not _ALLOWED_NAMES[name].is_file():
            problems.append(name + ": not readable")
    return problems


def map_lines(text: str | None = None) -> list[str]:
    text = load_map() if text is None else text
    return [ln for ln in text.splitlines() if " | " in ln]
