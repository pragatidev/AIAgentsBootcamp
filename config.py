"""The only place a model id lives.

Verify ids at record time. See docs/CURRENCY.md.
Never put a model name in a lecture title.
A missing key is not an error. Pytest stays green.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Local default. Free. No key. Verify the tag at record time.
# qwen3:8b is the student chat model: tool calling works on a 16 GB laptop.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "qwen3:8b")
NO_TOOLS_MODEL = os.environ.get("OLLAMA_NO_TOOLS_MODEL", "llama3.2:3b")

# Cloud ids stay empty until a live key is set. Verify at record time. Do not guess.
OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "")
ANTHROPIC_CHAT_MODEL = os.environ.get("ANTHROPIC_CHAT_MODEL", "")

# Local embedder for similarity recall. 768 dims. Verify the tag at record time.
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBED_DIMS = 768


def has_live_key() -> bool:
    """True only when a cloud key is present. Local Ollama does not count as a key."""
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return bool(openai_key or anthropic_key)


def _ollama_base() -> str:
    url = OLLAMA_BASE_URL.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    return url


def get_local_chat_model(**kwargs):
    """ChatOllama on the student default. Ignores hosted keys."""
    from langchain_ollama import ChatOllama

    params = {
        "model": kwargs.pop("model", CHAT_MODEL),
        "base_url": kwargs.pop("base_url", _ollama_base()),
        "temperature": kwargs.pop("temperature", 0),
    }
    params.update(kwargs)
    return ChatOllama(**params)


def get_chat_model(**kwargs):
    """Return a LangChain chat model for the configured provider.

    Hosted OpenAI or Anthropic when a key and a model id are set.
    Otherwise ChatOllama on the student default.
    """
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if openai_key and OPENAI_CHAT_MODEL and not kwargs.get("force_local"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0)
    if anthropic_key and ANTHROPIC_CHAT_MODEL and not kwargs.get("force_local"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=ANTHROPIC_CHAT_MODEL, temperature=0)
    kwargs.pop("force_local", None)
    return get_local_chat_model(**kwargs)

    return ChatOllama(model=CHAT_MODEL, base_url=_ollama_base(), temperature=0)


def tracing_callbacks():
    """Local jsonl tracer. Always on. No LangSmith key required."""
    from dataflow.ops.tracer import LocalTraceHandler

    return [LocalTraceHandler()]


def get_embeddings():
    """Local Ollama embeddings. nomic-embed-text is 768 dimensions."""
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=EMBED_MODEL, base_url=_ollama_base())
