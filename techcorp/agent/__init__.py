"""TechCorp agent lands here in Part 5."""

from techcorp.agent.context import DeskContext
from techcorp.agent.desk import DEFAULT_MIDDLEWARE, build_techcorp_desk, run_ticket
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT, WEAK_PROMPT, classify_prompt
from techcorp.agent.schemas import TicketClass

__all__ = [
    "DEFAULT_MIDDLEWARE",
    "DESK_SYSTEM_PROMPT",
    "DeskContext",
    "TicketClass",
    "WEAK_PROMPT",
    "build_techcorp_desk",
    "classify_prompt",
    "run_ticket",
]

