# %% [markdown]
# Get structured output with Pydantic, and watch it break.
#
# Ask for JSON matching TicketClass, parse it, print the object.
# Then a schema with a Literal the model cannot satisfy. Print the
# validation error verbatim, retry once with the error fed back, print
# the outcome.

# %%
from __future__ import annotations

from pathlib import Path
import json
import sys
from typing import Literal

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from openai import OpenAI
from pydantic import BaseModel, ValidationError

import config


class TicketClass(BaseModel):
    category: Literal["password", "vpn", "software", "access"]
    priority: Literal["low", "medium", "high"]
    user_id: str
    summary: str


class ImpossibleTicket(BaseModel):
    category: Literal["password", "vpn", "software", "access"]
    planet: Literal["must_be_pluto_office_wing"]


def _looks_like_json(raw: str) -> bool:
    """True when the outermost braces hold JSON that json.loads accepts."""
    import json as _json

    text = (raw or "").strip().strip("`")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return False
    try:
        _json.loads(text[start : end + 1])
        return True
    except ValueError:
        return False


def parse_ticket(raw: str, schema: type[BaseModel] = TicketClass) -> BaseModel:
    """Parse a model reply into a Pydantic object. Strips fences if present."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return schema.model_validate_json(text)


def raw_client() -> OpenAI:
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return OpenAI(base_url=base, api_key="ollama")


TICKET = (
    "TC-1001 from user E-4101: I forgot my laptop password after the "
    "long weekend. Please reset it."
)

# %%
client = raw_client()
schema = TicketClass.model_json_schema()
ask = (
    "Classify this TechCorp ticket as JSON matching this schema. "
    "No extra keys. No prose.\n"
    + json.dumps(schema)
    + "\n\nTicket:\n"
    + TICKET
)
ok_resp = client.chat.completions.create(
    model=config.CHAT_MODEL,
    messages=[{"role": "user", "content": ask}],
    temperature=0,
    max_tokens=1024,
    extra_body={"think": False},
)
ok_text = ok_resp.choices[0].message.content or ""
print("raw_json", ok_text)
if not ok_text.strip() or not _looks_like_json(ok_text):
    # A raw completion can come back empty or cut mid-string on some runs.
    # Ask again in JSON mode rather than crash on the parse.
    print("raw_json_empty" if not ok_text.strip() else "raw_json_invalid", True)
    chat = config.get_local_chat_model(
        reasoning=False, num_predict=256, format="json"
    )
    ok_text = str(chat.invoke(ask).content or "")
    print("json_via_langchain", ok_text)
parsed = parse_ticket(ok_text, TicketClass)
print("parsed_object", parsed)
print("parsed_dict", parsed.model_dump())

# %%
print("break_schema", "ImpossibleTicket requires planet Literal must_be_pluto_office_wing")
try:
    ImpossibleTicket.model_validate(parsed.model_dump())
    print("impossible_parsed", "unexpected success")
    validation_error = None
except ValidationError as exc:
    validation_error = str(exc)
    print("validation_error")
    print(validation_error)
bad_schema = ImpossibleTicket.model_json_schema()
bad_ask = (
    "Classify this TechCorp ticket as JSON matching this schema. "
    "You must fill every field with a value from its Literal list. "
    "No extra keys. No prose.\n"
    + json.dumps(bad_schema)
    + "\n\nTicket:\n"
    + TICKET
)
bad_resp = client.chat.completions.create(
    model=config.CHAT_MODEL,
    messages=[{"role": "user", "content": bad_ask}],
    temperature=0,
    max_tokens=1024,
    extra_body={"think": False},
)
bad_text = bad_resp.choices[0].message.content or ""
if not bad_text.strip():
    chat = config.get_local_chat_model(
        reasoning=False, num_predict=256, format="json"
    )
    bad_text = str(chat.invoke(bad_ask).content or "")
print("impossible_raw_json", bad_text)

# %%
retry_messages = [
    {"role": "user", "content": bad_ask},
    {"role": "assistant", "content": bad_text},
    {
        "role": "user",
        "content": (
            "That JSON failed Pydantic validation. Error:\n"
            + (validation_error or "unknown")
            + "\nReturn JSON that matches the schema, still filling planet "
            "from its Literal list. If you cannot, return JSON with planet "
            "set to must_be_pluto_office_wing anyway."
        ),
    },
]
retry_resp = client.chat.completions.create(
    model=config.CHAT_MODEL,
    messages=retry_messages,
    temperature=0,
    max_tokens=1024,
    extra_body={"think": False},
)
retry_text = retry_resp.choices[0].message.content or ""
if not retry_text.strip():
    chat = config.get_local_chat_model(
        reasoning=False, num_predict=256, format="json"
    )
    retry_text = str(chat.invoke(retry_messages).content or "")
print("retry_raw_json", retry_text)
try:
    retry_obj = parse_ticket(retry_text, ImpossibleTicket)
    print("retry_outcome", "parsed")
    print("retry_object", retry_obj)
except ValidationError as exc:
    print("retry_outcome", "still_invalid")
    print("retry_validation_error")
    print(str(exc))
