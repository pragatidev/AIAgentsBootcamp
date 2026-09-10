"""One door for chat models, embeddings, and agents. Ids live in .env."""

from __future__ import annotations

import os
from typing import Any, Sequence

from src.paths import ensure_sys_path, find_repo_root, load_dotenv

REPO_ROOT = ensure_sys_path()
load_dotenv(REPO_ROOT)


def _first(*names: str, default: str = "") -> str:
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return default


def provider_name() -> str:
    preferred = _first("PREFERRED_PROVIDER", "LLM_BACKEND").lower()
    if preferred in {"", "auto"}:
        if _first("ANTHROPIC_API_KEY", "LLM_API_KEY") and (
            _first("LLM_BACKEND").lower() in {"", "anthropic"}
            or preferred == "anthropic"
        ):
            if _first("LLM_BACKEND").lower() == "anthropic" or preferred == "anthropic":
                return "anthropic"
        if _first("ANTHROPIC_API_KEY") and preferred in {"", "auto", "anthropic"}:
            return "anthropic"
        if _first("OPENAI_API_KEY") and preferred in {"", "auto", "openai"}:
            return "openai"
        if preferred not in {"", "auto"}:
            return preferred
        return "ollama"
    return preferred


def get_llm(temperature: float = 0):
    """Chat model from .env. Swap provider by editing .env, not the notebook."""
    name = provider_name()
    if name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = _first(
            "ANTHROPIC_DEFAULT_MODEL",
            "LLM_MODEL",
            default="claude-haiku-4-5",
        )
        key = _first("ANTHROPIC_API_KEY", "LLM_API_KEY")
        if not key:
            raise RuntimeError("No Anthropic key. Set ANTHROPIC_API_KEY or LLM_API_KEY in .env")
        return ChatAnthropic(
            model=model,
            api_key=key,
            temperature=temperature,
        )
    if name == "openai":
        from langchain_openai import ChatOpenAI

        model = _first("OPENAI_DEFAULT_MODEL", "LLM_MODEL", default="gpt-4o-mini")
        key = _first("OPENAI_API_KEY", "LLM_API_KEY")
        if not key:
            raise RuntimeError("No OpenAI key. Set OPENAI_API_KEY in .env")
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": key,
            "temperature": temperature,
        }
        base = _first("OPENAI_BASE_URL", "LLM_BASE_URL")
        if base and "anthropic" not in base:
            kwargs["base_url"] = base
        return ChatOpenAI(**kwargs)
    if name in {"ollama", "local"}:
        from langchain_ollama import ChatOllama

        model = _first("OLLAMA_CHAT_MODEL", "OLLAMA_DEFAULT_MODEL", default="llama3.2")
        base = _first("OLLAMA_BASE_URL", default="http://localhost:11434")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        return ChatOllama(model=model, base_url=base, temperature=temperature)
    if name == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = _first("GOOGLE_DEFAULT_MODEL", default="gemini-2.0-flash")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=_first("GOOGLE_API_KEY"),
            temperature=temperature,
        )
    raise RuntimeError(
        f"Unknown provider {name!r}. Set PREFERRED_PROVIDER to anthropic, openai, or ollama."
    )


def get_embeddings():
    """Local embeddings. RAG notebooks do not need an OpenAI embed key."""
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        model = _first("EMBED_MODEL", default="sentence-transformers/all-MiniLM-L6-v2")
        return HuggingFaceEmbeddings(model_name=model)
    except Exception:
        from langchain_core.embeddings import FakeEmbeddings

        return FakeEmbeddings(size=384)


class AgentRunner:
    """create_agent graph with the old .run / string invoke shape notebooks used."""

    def __init__(self, graph: Any) -> None:
        self.graph = graph

    def invoke(self, payload: Any, **kwargs: Any) -> Any:
        if isinstance(payload, str):
            payload = {"messages": [{"role": "user", "content": payload}]}
        elif isinstance(payload, dict) and "messages" not in payload:
            text = payload.get("input") or payload.get("query") or ""
            payload = {"messages": [{"role": "user", "content": str(text)}]}
        return self.graph.invoke(payload, **kwargs)

    def run(self, text: str, **kwargs: Any) -> str:
        out = self.invoke(text, **kwargs)
        if isinstance(out, dict):
            messages = out.get("messages") or []
            if messages:
                last = messages[-1]
                content = getattr(last, "content", last)
                if isinstance(content, list):
                    return "".join(
                        (b.get("text") if isinstance(b, dict) else str(b)) for b in content
                    )
                return str(content)
            return str(out.get("output", out))
        return str(out)


def get_agent(tools: Sequence[Any], system_prompt: str | None = None) -> AgentRunner:
    """Replacement for initialize_agent. Uses langchain.agents.create_agent."""
    from langchain.agents import create_agent

    graph = create_agent(
        model=get_llm(),
        tools=list(tools),
        system_prompt=system_prompt or "You are a helpful assistant. Use tools when they help.",
    )
    return AgentRunner(graph)


def boot_notebook() -> None:
    """Call from the first notebook cell. Safe to call twice."""
    ensure_sys_path(find_repo_root())
    load_dotenv()
