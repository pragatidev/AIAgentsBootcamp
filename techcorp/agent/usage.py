"""What a model call cost: read it off one reply, or add it up over a whole run."""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


def read_usage(reply: Any) -> dict:
    """The token counts on one AI message, the kinds of blocks in it, and how much of it you can see."""
    usage = getattr(reply, "usage_metadata", None) or {}
    blocks = list(getattr(reply, "content_blocks", None) or [])
    reasoning = "".join(str(b.get("reasoning") or "") for b in blocks if b.get("type") == "reasoning")
    visible = " ".join(str(b.get("text") or "") for b in blocks if b.get("type") == "text")
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "blocks": [b.get("type") for b in blocks],
        "reasoning_chars": len(reasoning),
        "visible_words": len(visible.split()),
    }


class TokenCounter(BaseCallbackHandler):
    """Adds up the tokens of every model call in a run. Pass it in config={"callbacks": [counter]}."""

    def __init__(self) -> None:
        super().__init__()
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.calls = 0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        # Chat models end here too: LangChain has no on_chat_model_end callback.
        self.calls += 1
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                usage = getattr(message, "usage_metadata", None) or {}
                self.input_tokens += int(usage.get("input_tokens") or 0)
                self.output_tokens += int(usage.get("output_tokens") or 0)
                self.total_tokens += int(usage.get("total_tokens") or 0)

    def over(self, limit: int) -> bool:
        """True once the run has used more tokens than the limit."""
        return self.total_tokens > limit
