"""Helpers for the LangGraph streaming lab tests (LG-R2, Section 15).

PiecewiseToolChatModel: the house ScriptedToolChatModel streams a tool call whole, in one chunk, the way qwen3:8b on
Ollama sends it. A provider that streams the arguments sends the id and the name first and then the arguments in pieces.
This model plays the same script in that second shape, so a lab that reads streamed tool calls is tested on both.
Plain text replies stream one word per chunk.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessageChunk
from langchain_core.messages.tool import tool_call_chunk
from langchain_core.outputs import ChatGenerationChunk

from tests.fixtures.fake_model import ScriptedToolChatModel


class PiecewiseToolChatModel(ScriptedToolChatModel):
    """ScriptedToolChatModel whose stream sends a tool call as id and name first, then the arguments in pieces."""

    piece_size: int = 8

    def _stream(self, messages: list[Any], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any):
        message = self._generate(messages, stop=stop, run_manager=run_manager, **kwargs).generations[0].message
        if getattr(message, "tool_calls", None):
            for index, call in enumerate(message.tool_calls):
                first = tool_call_chunk(name=call["name"], args="", id=call["id"], index=index)
                yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=[first]))
                args = json.dumps(call["args"])
                for start in range(0, len(args), self.piece_size):
                    piece = tool_call_chunk(name=None, args=args[start : start + self.piece_size], id=None, index=index)
                    yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=[piece]))
            return
        words = str(message.content or "").split(" ")
        for n, word in enumerate(words):
            yield ChatGenerationChunk(message=AIMessageChunk(content=word if n == len(words) - 1 else word + " "))
