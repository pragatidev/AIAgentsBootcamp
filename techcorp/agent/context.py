"""Runtime envelope for a TechCorp desk run. Not checkpointed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DeskContext:
    user_id: str | None = None
    region: str = "US"
    model: Any = None
