"""Fixture chat model for pytest. Returns a fixed route. Not a keyword stand-in in the graph."""

from __future__ import annotations

from typing import Any


class FakeChatModel:
    """Duck-typed chat model. with_structured_output returns the fixed route."""

    def __init__(self, route: str = "orders") -> None:
        self.route = route

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        route = self.route

        class _Runner:
            def invoke(self, messages: Any, **kw: Any) -> Any:
                payload = {"route": route}
                if hasattr(schema, "model_validate"):
                    return schema.model_validate(payload)
                try:
                    return schema(**payload)
                except Exception:
                    return payload

        return _Runner()
