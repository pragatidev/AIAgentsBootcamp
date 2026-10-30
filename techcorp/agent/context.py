"""Runtime envelope for a TechCorp desk run. Not checkpointed.

The caller fills it, never the model: who is asking (user_id), their role and region,
who approved a parked write (approver), and the ids that tie a run to its ticket and request.
Every field has a default, so DeskContext(user_id="E-4101") still builds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DeskContext:
    user_id: str | None = None
    region: str = "US"
    model: Any = None
    role: str = "employee"
    approver: str | None = None
    ticket_id: str | None = None
    request_id: str | None = None
