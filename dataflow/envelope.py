"""The request envelope: the facts about one request that the caller's system fills in.

The model never writes these. A tool reads them through its runtime (ToolRuntime on a
create_agent desk, Runtime in a graph node), and code decides from them who is asking
and what that caller may read or change. This module imports no agent and no graph,
so the create_agent desk and every DataFlow graph share one class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DeskContext:
    model: Any = None
    customer_id: str = "anon"
    actor_id: str = "anon"
    user_id: str = ""
