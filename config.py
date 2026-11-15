"""The only place a model id lives.

Model ids change. Copy a live id from the provider's page. See docs/CURRENCY.md.
Never put a model name in a lecture title.
A missing key is not an error. Pytest stays green.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    """Load .env from the repo root. Never print values. Do not overwrite."""
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# Local default. No key and no per-token price; it runs on your own machine.
# qwen3:8b is the student chat model: tool calling works on a 16 GB laptop.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "qwen3:8b")
# Cap on tokens one local reply may generate. Ollama serves one request at a
# time, and a thinking model that loops can hold that slot for twenty minutes.
# 4096 covers every lab reply in this course with room for the thinking block.
NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "4096"))
NO_TOOLS_MODEL = os.environ.get("OLLAMA_NO_TOOLS_MODEL", "llama3.2:3b")

# Cloud ids stay empty until you set a key. Copy the exact id from the provider's page. Do not guess.
OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "")
ANTHROPIC_CHAT_MODEL = os.environ.get("ANTHROPIC_CHAT_MODEL", "")
# Google Gemini needs one extra package: pip install langchain-google-genai (tested on 4.4.0).
# Use it for the chat model only; keep embeddings on nomic-embed-text so every index stays 768 wide.
GOOGLE_CHAT_MODEL = os.environ.get("GOOGLE_CHAT_MODEL", "")

# Embeddings. Local default is nomic-embed-text (768 dimensions on Ollama).
# faiss_index measures the width at build time; do not copy 768 elsewhere.
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OPENAI_EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "")
EMBED_DIMENSIONS = 768
EMBED_DIMS = EMBED_DIMENSIONS  # older name kept for Part 4 labs


def has_live_key() -> bool:
    """True only when a cloud key is present. Local Ollama does not count as a key."""
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    google_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    return bool(openai_key or anthropic_key or google_key)


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
        "num_predict": kwargs.pop("num_predict", NUM_PREDICT),
    }
    params.update(kwargs)
    return ChatOllama(**params)


def _anthropic_chat(model: str):
    """ChatAnthropic at temperature 0, or at the model's default if the library refuses 0.

    Some Claude models only take the default temperature. langchain-anthropic
    knows which, and raises before any request, so ask it here.
    """
    from langchain_anthropic import ChatAnthropic

    chat = ChatAnthropic(model=model, temperature=0)
    check = getattr(chat, "_assert_valid_model_configuration", None)
    if check is None:
        return chat
    try:
        check({})
    except ValueError as err:
        if "temperature" not in str(err):
            raise
        return ChatAnthropic(model=model)
    return chat


def _google_chat(model: str, api_key: str):
    """ChatGoogleGenerativeAI at temperature 0. The package is optional, so say how to get it."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as err:
        raise ImportError(
            "GOOGLE_API_KEY and GOOGLE_CHAT_MODEL are set, but langchain-google-genai is not installed. "
            "Run: pip install langchain-google-genai"
        ) from err
    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0)


_warned_no_model_id: set[str] = set()


def _warn_key_without_model_id(provider: str) -> None:
    """One plain line, once per provider, when a key is set but its model id is not."""
    if provider in _warned_no_model_id:
        return
    _warned_no_model_id.add(provider)
    print(
        f"warning: {provider}_API_KEY is set but {provider}_CHAT_MODEL is empty, "
        f"so this run uses the local model {CHAT_MODEL}. "
        f"Set {provider}_CHAT_MODEL in .env to use the hosted model.",
        file=sys.stderr,
    )


def get_chat_model(**kwargs):
    """Return a LangChain chat model for the configured provider.

    Hosted OpenAI, Anthropic or Google when a key and a model id are set (checked in that order).
    Otherwise ChatOllama on the student default.
    """
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    google_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not kwargs.get("force_local"):
        if openai_key and not OPENAI_CHAT_MODEL:
            _warn_key_without_model_id("OPENAI")
        if anthropic_key and not ANTHROPIC_CHAT_MODEL:
            _warn_key_without_model_id("ANTHROPIC")
        if google_key and not GOOGLE_CHAT_MODEL:
            _warn_key_without_model_id("GOOGLE")
    if openai_key and OPENAI_CHAT_MODEL and not kwargs.get("force_local"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0)
    if anthropic_key and ANTHROPIC_CHAT_MODEL and not kwargs.get("force_local"):
        return _anthropic_chat(ANTHROPIC_CHAT_MODEL)
    if google_key and GOOGLE_CHAT_MODEL and not kwargs.get("force_local"):
        return _google_chat(GOOGLE_CHAT_MODEL, google_key)
    kwargs.pop("force_local", None)
    return get_local_chat_model(**kwargs)


def tracing_callbacks():
    """Local jsonl tracer, always on. LangChainTracer too when a key is set."""
    from dataflow.ops.tracer import LocalTraceHandler
    from dataflow.tracing import langsmith_tracer_if_key

    handlers: list = [LocalTraceHandler()]
    hosted = langsmith_tracer_if_key()
    if hosted is not None:
        handlers.append(hosted)
    return handlers


def get_embeddings():
    """Return the desk embedder. Same model must build the index and query it.

    Hosted OpenAI when a key and OPENAI_EMBED_MODEL are set.
    Otherwise OllamaEmbeddings on nomic-embed-text.
    """
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    openai_embed = os.environ.get("OPENAI_EMBED_MODEL", OPENAI_EMBED_MODEL).strip()
    if openai_key and openai_embed:
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=openai_embed)
    from langchain_ollama import OllamaEmbeddings

    model = os.environ.get("OLLAMA_EMBED_MODEL", EMBED_MODEL)
    return OllamaEmbeddings(model=model, base_url=_ollama_base())


# Thinking and reply length on every provider (added 2026-11-15, from a student's question).
# get_chat_model above picks the provider. On the local path it hands reasoning= and num_predict= to
# ChatOllama; its three hosted branches build their model without them. The get_chat_model below runs
# the one above, then gives the hosted model the same two settings in that provider's own words:
#   num_predict=N    at most N output tokens, thinking included: num_predict on Ollama, max_tokens on
#                    OpenAI and Anthropic, max_output_tokens on Google. Left out, a hosted model keeps
#                    its library's default.
#   reasoning=False  thinking off. Where a model cannot switch it off, the least thinking it allows,
#                    and one warning line says so.
#   reasoning=True   thinking on.
#   left out         the model's own default, exactly as before.
# Which model takes which value comes from each provider's docs, read 2026-11-15.
_pick_chat_model = get_chat_model
_warned_thinking: set[str] = set()

# OpenAI. Older GPT-4 and GPT-3.5 models have no thinking to switch. gpt-6-astra and gpt-6.1-sol list
# low as their lowest effort, no "none"; every other model gets "none".
_OPENAI_NO_THINKING = ("gpt-4", "gpt-3.5", "chatgpt-4o")
_OPENAI_LOWEST_IS_LOW = ("gpt-6-astra", "gpt-6.1-sol", "o1", "o3", "o4")
# The first GPT-5 models (gpt-5, gpt-5-mini, gpt-5-nano) came before "none"; "minimal" is their least.
# gpt-5.1 and later take "none", so only "gpt-5" itself and "gpt-5-..." match here, never "gpt-5.1".
_OPENAI_LOWEST_IS_MINIMAL = ("gpt-5-",)
# Anthropic. These refuse thinking {"type": "disabled"}; low effort is their least thinking.
_CLAUDE_CANNOT_SWITCH_OFF = ("claude-opus-5-5", "claude-fable-5", "claude-mythos")
# Sonnet 5.5 refuses "disabled" too; "between_tools" switches off the thinking before its answer.
_CLAUDE_BETWEEN_TOOLS = ("claude-sonnet-5-5",)
# Claude's thinking docs: these models answer 400 to any non-default temperature, thinking or not, so
# the temperature 0 that _anthropic_chat sets is taken off again for them.
_CLAUDE_DEFAULT_TEMPERATURE_ONLY = (
    "claude-fable", "claude-mythos", "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
    "claude-sonnet-5", "claude-haiku-5",
)
# These refuse adaptive thinking; they think only with a budget of at least 1,024 tokens.
_CLAUDE_BUDGET_ONLY = (
    "claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5",
    "claude-opus-4-1", "claude-opus-4-0", "claude-sonnet-4-0", "claude-opus-4-2", "claude-sonnet-4-2",
)
# Google. Gemini has no level that switches thinking off. These four take "minimal", the others "low".
# gemini-2.5-flash-lite is the one model that does not think unless asked.
_GEMINI_MINIMAL = ("gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash")
_GEMINI_OFF_BY_DEFAULT = ("gemini-2.5-flash-lite",)


def _warn_thinking(model: str, said: str) -> None:
    """One plain line, once per model, when reasoning=False cannot switch thinking fully off."""
    if model in _warned_thinking:
        return
    _warned_thinking.add(model)
    print(f"warning: {model} {said}", file=sys.stderr)


def _openai_thinking(model: str, on: bool) -> dict:
    name = model.lower()
    if name.startswith(_OPENAI_NO_THINKING):
        return {}
    if on:
        return {"reasoning_effort": "medium"}
    if name.startswith(_OPENAI_LOWEST_IS_LOW):
        _warn_thinking(model, 'cannot switch thinking off, so reasoning=False asks for reasoning_effort "low".')
        return {"reasoning_effort": "low"}
    if name == "gpt-5" or name.startswith(_OPENAI_LOWEST_IS_MINIMAL):
        _warn_thinking(model, 'cannot switch thinking off, so reasoning=False asks for reasoning_effort "minimal".')
        return {"reasoning_effort": "minimal"}
    return {"reasoning_effort": "none"}


def _anthropic_thinking(model: str, on: bool, max_tokens: int) -> dict:
    if model.startswith(_CLAUDE_BUDGET_ONLY):
        if not on:
            return {"thinking": {"type": "disabled"}}
        if max_tokens <= 1024:
            raise ValueError(
                f"{model} thinks only with a budget of at least 1024 tokens, inside max_tokens. "
                "Raise num_predict above 1024, or use reasoning=False."
            )
        return {"thinking": {"type": "enabled", "budget_tokens": 1024}, "temperature": None}
    if on:
        return {"thinking": {"type": "adaptive"}, "temperature": None}
    if model.startswith(_CLAUDE_CANNOT_SWITCH_OFF):
        _warn_thinking(model, 'cannot switch thinking off, so reasoning=False asks for effort "low".')
        return {"thinking": {"type": "adaptive"}, "reasoning_effort": "low"}
    if model.startswith(_CLAUDE_BETWEEN_TOOLS):
        _warn_thinking(model, 'cannot switch thinking fully off, so reasoning=False sends "between_tools".')
        return {"thinking": {"type": "between_tools"}}
    return {"thinking": {"type": "disabled"}}


def _google_thinking(model: str, on: bool) -> dict:
    name = model.removeprefix("models/")
    if name.startswith(_GEMINI_OFF_BY_DEFAULT):
        return {"reasoning_effort": "medium"} if on else {}
    if on:
        return {}
    lowest = "minimal" if name.startswith(_GEMINI_MINIMAL) else "low"
    _warn_thinking(name, f'cannot switch thinking off, so reasoning=False asks for thinking_level "{lowest}".')
    return {"reasoning_effort": lowest}


def get_chat_model(**kwargs):
    """The chooser above, with reasoning= and num_predict= kept on every provider, hosted ones too."""
    chat = _pick_chat_model(**kwargs)
    kind = type(chat).__name__
    if kind == "ChatOllama":
        return chat
    reasoning = kwargs.get("reasoning")
    num_predict = kwargs.get("num_predict")
    update: dict = {}
    if kind == "ChatAnthropic" and chat.model.startswith(_CLAUDE_DEFAULT_TEMPERATURE_ONLY):
        update["temperature"] = None
    if num_predict is not None:
        update["max_output_tokens" if kind == "ChatGoogleGenerativeAI" else "max_tokens"] = int(num_predict)
    if reasoning is not None:
        on = bool(reasoning)
        if kind == "ChatOpenAI":
            update.update(_openai_thinking(chat.model_name, on))
        elif kind == "ChatAnthropic":
            update.update(_anthropic_thinking(chat.model, on, update.get("max_tokens", chat.max_tokens)))
        elif kind == "ChatGoogleGenerativeAI":
            update.update(_google_thinking(chat.model, on))
    return chat.model_copy(update=update) if update else chat
