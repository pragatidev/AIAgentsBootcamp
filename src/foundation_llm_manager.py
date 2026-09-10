"""Back-compat for the cost-free lecture. New notebooks import src.llm.get_llm."""

from src.llm import get_llm as get_llm
from src.llm import provider_name
from src.paths import find_repo_root, load_dotenv

load_dotenv(find_repo_root())


def get_manager(daily_budget: float = 5.0):
    return _Manager()


class _Manager:
    def get_llm(self, provider=None, model=None):
        return get_llm()

    def chat(self, message: str, **kwargs) -> str:
        result = get_llm().invoke(message)
        return getattr(result, "content", str(result))

    def show_status(self) -> None:
        print("provider", provider_name())
        print("repo", find_repo_root())


def chat(message: str, **kwargs) -> str:
    return get_manager().chat(message, **kwargs)


def show_status() -> None:
    get_manager().show_status()


def setup_foundation(daily_budget: float = 5.0):
    mgr = get_manager(daily_budget)
    print("LLM foundation ready.")
    mgr.show_status()
    return mgr
