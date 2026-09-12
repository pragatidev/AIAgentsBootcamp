"""Fat instruction file and the map. Content lives on disk; the map is a table of contents."""

from __future__ import annotations

from pathlib import Path

KB = Path(__file__).resolve().parents[1] / "knowledge_base"
WIKI = Path(__file__).resolve().parents[1] / "wiki"

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


def map_lines() -> list[str]:
    return [ln for ln in MAP.splitlines() if " | " in ln]
