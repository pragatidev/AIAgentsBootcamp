# %% [markdown]
# with_structured_output on a ticket classifier.
#
# When this works, four tickets come back as TicketClass objects and
# the JSON schema the model receives is printed. The break is a schema
# whose Literal omits vpn, sent the VPN ticket.

# %%
from pathlib import Path
import json
import sys
from typing import Literal

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from pydantic import BaseModel, Field

import config
from techcorp.agent.schemas import TicketClass

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
wanted = {"TC-1001", "TC-1002", "TC-1003", "TC-1004"}
tickets = []
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row["ticket_id"] in wanted:
        tickets.append(row)
tickets.sort(key=lambda row: row["ticket_id"])

print("model", config.CHAT_MODEL)
print("schema", TicketClass.model_json_schema())
print("Literal", TicketClass.model_fields["category"].annotation)

model = config.get_chat_model()
classifier = model.with_structured_output(TicketClass)

# %%
for row in tickets:
    text = f"Ticket {row['ticket_id']}: {row['text']}"
    obj = classifier.invoke(text)
    print("ticket_id", row["ticket_id"])
    print("text", row["text"])
    print("object", obj)
    print("type", type(obj))
    print("type_name", type(obj).__name__)
    if hasattr(obj, "model_dump"):
        print("dump", obj.model_dump())
    print("---")

# %%
print("BREAK: Literal that omits vpn")


class TicketClassNoVpn(BaseModel):
    category: Literal["password", "access", "software", "other"] = Field(
        description="Which desk owns this ticket"
    )
    priority: Literal["low", "normal", "high"] = Field(
        description="How urgent the ticket is"
    )
    needs_human: bool = Field(description="True when a person must take the ticket")
    reason: str = Field(description="One short reason for the classification")


print("broken_schema", TicketClassNoVpn.model_json_schema())
vpn = next(row for row in tickets if row["ticket_id"] == "TC-1002")
broken = model.with_structured_output(TicketClassNoVpn)
try:
    obj = broken.invoke(f"Ticket {vpn['ticket_id']}: {vpn['text']}")
    print("broken_object", obj)
    print("broken_type", type(obj))
    if hasattr(obj, "model_dump"):
        print("broken_dump", obj.model_dump())
except Exception as err:
    print("broken_error_type", type(err).__name__)
    print("broken_error", err)
