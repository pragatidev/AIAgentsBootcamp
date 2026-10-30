# %%
"""Lab 4.10: with_structured_output on a ticket classifier.

What we build: you write the form the desk fills in for every ticket, a Pydantic class with a fixed
list of categories and a priority with bands, hand it to the real model, and classify five TechCorp
tickets into objects your code can trust. Then the same form becomes the final answer of create_agent.

What you learn: a schema is a form the model fills in. A Literal keeps a field on its list, and a field
the form leaves loose the model fills as it likes, so the description is where you define it. And the
same form works two ways: on a bare model, and as create_agent's response_format.

What will be true on your screen: the five category values the model is allowed, one row per ticket
with its category, priority and whether it matches the category a person would pick, a
categories_right count out of four, and a TicketClass object in structured_response.
"""

from pathlib import Path
from typing import Literal
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

import config
from techcorp.agent.prompts import classify_prompt


# %%
# TYPE THIS: TicketClass. The class line and docstring are given; you type the four fields.
# Its finished copy is techcorp/agent/schemas.py.
class TicketClass(BaseModel):
    """One TechCorp IT ticket, classified into a fixed form."""

    category: Literal["password", "access", "vpn", "software", "other"] = Field(
        description="Which desk owns this ticket"
    )
    priority: Literal["low", "normal", "high"] = Field(
        description=(
            "high: many people are blocked or it is a security risk; "
            "normal: one person is blocked; low: it can wait a day"
        )
    )
    needs_human: bool = Field(
        description="True when a person must take the ticket"
    )
    reason: str = Field(description="One short reason for the classification")


# BREAK: delete "vpn" from the category list above and run. The VPN ticket lands in another box, the
# model raises nothing, and python -m pytest tests/test_lab_05_10.py -q goes red. Put "vpn" back.

print("category_values", list(TicketClass.model_json_schema()["properties"]["category"]["enum"]))

# %%
tickets = (root / "techcorp" / "data" / "tickets.jsonl").read_text(encoding="utf-8").splitlines()
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets)}
# The category a person reading each ticket would pick. TC-1013 is written for this lab: it carries urgency.
EXPECTED = {"TC-1001": "password", "TC-1002": "vpn", "TC-1003": "software", "TC-1004": "access"}
cases = [(tid, by_id[tid]["text"]) for tid in EXPECTED]
cases.append(("TC-1013", "VPN is down for the whole finance floor and the Q3 close is today."))

model = config.get_chat_model()
print("model", type(model).__name__, getattr(model, "model", None) or getattr(model, "model_name", None))
classifier = model.with_structured_output(TicketClass)

right = 0
for ticket_id, text in cases:
    form = classifier.invoke([SystemMessage(content=classify_prompt()), HumanMessage(content=f"Ticket {ticket_id}: {text}")])
    match = EXPECTED.get(ticket_id) == form.category if ticket_id in EXPECTED else None
    right += bool(match)
    print("row", ticket_id, type(form).__name__, form.category, form.priority, "needs_human", form.needs_human, "match", match)
print("categories_right", f"{right}/{len(EXPECTED)}")

# %%
# The same form as create_agent's final answer. ToolStrategy is named so every model fills it the same way.
agent = create_agent(model=model, tools=[], system_prompt=classify_prompt(), response_format=ToolStrategy(TicketClass))
out = agent.invoke({"messages": [HumanMessage(content=f"Ticket TC-1002: {by_id['TC-1002']['text']}")]})
print("structured_response", type(out["structured_response"]).__name__, out["structured_response"])
