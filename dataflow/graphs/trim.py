"""Trim a long DataFlow thread: summarize older messages, keep the rest under budget."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

import tiktoken
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    trim_messages,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.runtime import Runtime

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext

TOKEN_BUDGET = 200
KEEP_RECENT = 4
SUMMARIZE_PROMPT = (
    "You summarize a DataFlow support thread. "
    "Write two short sentences. Keep order ids and what the customer asked. "
    "No preamble."
)


class TrimState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    summary: str


class TrimInput(TypedDict):
    messages: Annotated[list, add_messages]


class TrimOutput(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    summary: str


class SummarizeScratch(TypedDict):
    draft: str
    tokens_before: int


class SummarizeUpdate(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    summary: str
    draft: str
    tokens_before: int


def _encoding():
    return tiktoken.get_encoding("cl100k_base")


def _content_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content", "")
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return str(content or "")


def count_message_tokens(messages: Any) -> int:
    """Real cl100k_base counts. Accepts one message or a list."""
    if messages is None:
        return 0
    if isinstance(messages, (str, bytes)) or isinstance(messages, BaseMessage):
        batch = [messages]
    elif isinstance(messages, dict):
        batch = [messages]
    else:
        try:
            batch = list(messages)
        except TypeError:
            batch = [messages]
    enc = _encoding()
    total = 0
    for message in batch:
        if isinstance(message, (str, bytes)):
            text = message.decode("utf-8") if isinstance(message, bytes) else message
            role = ""
        else:
            text = _content_text(message)
            role = str(getattr(message, "type", "") or "")
        total += len(enc.encode(f"{role}: {text}"))
    return total


def summarize(
    state: TrimState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> SummarizeUpdate:
    """Summarize older turns, trim the thread, keep draft and tokens_before private."""
    chat = model
    if chat is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        chat = getattr(ctx, "model", None) if ctx is not None else None
    if chat is None:
        chat = get_chat_model()

    messages = list(state.get("messages") or [])
    tokens_before = count_message_tokens(messages)

    if len(messages) > KEEP_RECENT:
        older = messages[:-KEEP_RECENT]
        recent = messages[-KEEP_RECENT:]
    else:
        older = []
        recent = messages

    if older:
        older_text = "\n".join(
            f"{getattr(m, 'type', 'msg')}: {_content_text(m)}" for m in older
        )
        result = chat.invoke(
            [
                SystemMessage(content=SUMMARIZE_PROMPT),
                HumanMessage(content=older_text),
            ]
        )
        draft = _content_text(result).strip()
    else:
        draft = "No older messages to summarize."

    clip = draft
    if len(clip) > 300:
        clip = clip[:300]
    summary_msg = SystemMessage(content=f"Earlier on this DataFlow thread: {clip}")
    kept = trim_messages(
        [summary_msg, *recent],
        max_tokens=TOKEN_BUDGET,
        token_counter=count_message_tokens,
        strategy="last",
        start_on="human",
        include_system=True,
        allow_partial=False,
    )
    return {
        "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *kept],
        "summary": draft,
        "draft": draft,
        "tokens_before": tokens_before,
    }


def build_trim_graph(*, model: Any = None):
    builder = StateGraph(
        TrimState,
        context_schema=DeskContext,
        input_schema=TrimInput,
        output_schema=TrimOutput,
    )

    def summarize_node(
        state: TrimState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> SummarizeUpdate:
        return summarize(state, runtime=runtime, model=model)

    builder.add_node("summarize", summarize_node, input_schema=TrimInput)
    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()
