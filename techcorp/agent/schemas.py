"""Typed forms the TechCorp desk asks a model to fill in."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TicketClass(BaseModel):
    """One TechCorp IT ticket, classified into a fixed form."""

    category: Literal["password", "access", "vpn", "software", "other"] = Field(
        description="Which desk owns this ticket"
    )
    priority: Literal["low", "normal", "high"] = Field(
        description="How urgent the ticket is"
    )
    needs_human: bool = Field(
        description="True when a person must take the ticket"
    )
    reason: str = Field(description="One short reason for the classification")
