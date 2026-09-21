"""Back-compat for the cost-free lecture. New notebooks import src.llm.get_llm."""

import os
from datetime import date

from src.llm import get_llm as get_llm
from src.llm import provider_name
from src.paths import find_repo_root, load_dotenv

load_dotenv(find_repo_root())

# Price per million tokens (input, output) in US dollars, used only for the budget
# printout. Local Ollama is free. These are the published list prices for the default
# models in .env.sample; if you change model, set LLM_PRICE_IN and LLM_PRICE_OUT in .env.
_PRICES = {
    "ollama": (0.0, 0.0),
    "local": (0.0, 0.0),
    "anthropic": (1.0, 5.0),  # claude-haiku-4-5
    "openai": (0.15, 0.60),  # gpt-4o-mini
}


def _text(result) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        content = "".join((b.get("text") if isinstance(b, dict) else str(b)) for b in content)
    return str(content)


def _price(provider: str) -> tuple[float, float]:
    base = _PRICES.get(provider, (0.0, 0.0))
    try:
        return (float(os.getenv("LLM_PRICE_IN", base[0])), float(os.getenv("LLM_PRICE_OUT", base[1])))
    except ValueError:
        return base


class _Manager:
    def __init__(self, daily_budget: float = 5.0) -> None:
        self.daily_budget = daily_budget
        self.day = date.today()
        self.spent = 0.0

    def get_llm(self, provider=None, model=None):
        return get_llm()

    def _run(self, llm, provider: str, message: str) -> str:
        result = llm.invoke(message)
        usage = getattr(result, "usage_metadata", None) or {}
        p_in, p_out = _price(provider)
        if self.day != date.today():
            self.day, self.spent = date.today(), 0.0
        self.spent += (usage.get("input_tokens", 0) * p_in + usage.get("output_tokens", 0) * p_out) / 1_000_000
        return _text(result)

    def chat(self, message: str, task_type: str | None = None, **kwargs) -> str:
        return self._run(get_llm(), provider_name(), message)

    def free_chat(self, message: str) -> str:
        """Always the local Ollama model, so it costs nothing. Needs `ollama serve`."""
        from langchain_ollama import ChatOllama

        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").removesuffix("/v1")
        model = os.getenv("OLLAMA_CHAT_MODEL") or os.getenv("OLLAMA_DEFAULT_MODEL") or "llama3.2"
        return self._run(ChatOllama(model=model, base_url=base, temperature=0), "ollama", message)

    def get_daily_spending(self) -> float:
        return self.spent

    def get_remaining_budget(self) -> float:
        return max(self.daily_budget - self.spent, 0.0)

    def show_status(self) -> None:
        print("provider", provider_name())
        print("repo", find_repo_root())
        print(f"spent today ${self.spent:.4f} of ${self.daily_budget:.2f}")


_MANAGER: _Manager | None = None


def get_manager(daily_budget: float | None = None) -> _Manager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = _Manager(daily_budget if daily_budget is not None else 5.0)
    elif daily_budget is not None:
        _MANAGER.daily_budget = daily_budget
    return _MANAGER


def chat(message: str, **kwargs) -> str:
    return get_manager().chat(message, **kwargs)


def free_chat(message: str) -> str:
    return get_manager().free_chat(message)


# One provider comes from .env, so every task type uses it. The names stay so the
# lecture can show the idea of routing a task to the right model.
def budget_chat(message: str) -> str:
    return chat(message, task_type="budget")


def speed_chat(message: str) -> str:
    return chat(message, task_type="speed")


def quality_chat(message: str) -> str:
    return chat(message, task_type="quality")


def coding_chat(message: str) -> str:
    return chat(message, task_type="coding")


def reasoning_chat(message: str) -> str:
    return chat(message, task_type="reasoning")


def show_status() -> None:
    get_manager().show_status()


def setup_foundation(daily_budget: float | None = None):
    mgr = get_manager(daily_budget)
    print("LLM foundation ready.")
    mgr.show_status()
    return mgr
