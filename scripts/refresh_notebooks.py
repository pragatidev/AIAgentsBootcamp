# One-time / re-runnable: point every live notebook at src.llm.get_llm.
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BOOT = (
    "from src.paths import ensure_sys_path, find_repo_root\n"
    "ensure_sys_path(find_repo_root())\n"
    "from src.llm import REPO_ROOT, get_agent, get_embeddings, get_llm\n"
    "llm = get_llm()\n"
)

SKIP_DIRS = {".venv", "__pycache__", ".git", "northstar", "labs", "tests"}


def cell_text(cell: dict) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


def set_cell_text(cell: dict, text: str) -> None:
    cell["source"] = [line + "\n" for line in text.split("\n")[:-1]] + (
        [text.split("\n")[-1]] if text.split("\n")[-1] != "" else []
    )
    if text.endswith("\n"):
        if cell["source"] and not str(cell["source"][-1]).endswith("\n"):
            cell["source"][-1] = str(cell["source"][-1]) + "\n"


def replace_initialize(src: str) -> str:
    token = "initialize_agent("
    out = []
    i = 0
    while True:
        j = src.find(token, i)
        if j < 0:
            out.append(src[i:])
            break
        k = j + len(token)
        depth = 1
        while k < len(src) and depth:
            if src[k] == "(":
                depth += 1
            elif src[k] == ")":
                depth -= 1
            k += 1
        body = src[j + len(token) : k - 1]
        match = re.search(r"tools\s*=\s*(\[[^\]]*\]|[A-Za-z_][\w]*)", body)
        arg = match.group(1).strip() if match else "tools"
        out.append(src[i:j])
        out.append(f"get_agent({arg})")
        i = k
    return "".join(out)


def replace_call(src: str, func_name: str, replacement: str) -> str:
    token = func_name + "("
    out = []
    i = 0
    while True:
        j = src.find(token, i)
        if j < 0:
            out.append(src[i:])
            break
        # keep assignment target if present on same statement start
        k = j + len(token)
        depth = 1
        while k < len(src) and depth:
            if src[k] == "(":
                depth += 1
            elif src[k] == ")":
                depth -= 1
            k += 1
        out.append(src[i:j])
        out.append(replacement)
        i = k
    return "".join(out)


def rewrite_code(src: str) -> str:
    src = re.sub(r"from langchain\.llms import OpenAI\s*", "", src)
    src = re.sub(r"from langchain\.llms import Ollama\s*", "", src)
    src = re.sub(r"from langchain\.chat_models import ChatOpenAI\s*", "", src)
    src = re.sub(r"from langchain_openai import ChatOpenAI, OpenAIEmbeddings\s*", "", src)
    src = re.sub(r"from langchain_openai import ChatOpenAI\s*", "", src)
    src = re.sub(r"from langchain_openai import OpenAIEmbeddings\s*", "", src)
    src = re.sub(
        r"from langchain\.agents import initialize_agent, AgentType\s*",
        "",
        src,
    )
    src = re.sub(r"from langchain\.agents import initialize_agent\s*", "", src)
    src = re.sub(r"from langchain\.agents\.agent_types import AgentType\s*", "", src)
    src = re.sub(r"from langchain_ollama import OllamaLLM\s*", "", src)
    src = replace_call(src, "ChatOpenAI", "get_llm()")
    src = replace_call(src, "OpenAIEmbeddings", "get_embeddings()")
    src = re.sub(r"\bOpenAI\(", "get_llm(", src)
    src = re.sub(r"OllamaLLM\(", "get_llm(", src)
    src = replace_initialize(src)
    # TalentFlow helper: always env
    src = re.sub(
        r"def setup_llm\([\s\S]*?return None, \"none\"",
        "def setup_llm(use_openai=False):\n    return get_llm(), \"env\"",
        src,
        count=1,
    )
    # common leftover get_llm(api_key=...) from OpenAI(
    src = re.sub(r"get_llm\([^)]*\)", "get_llm()", src)
    src = re.sub(r"get_embeddings\([^)]*\)", "get_embeddings()", src)
    src = re.sub(r"openai_api_key = os\.getenv\(\"OPENAI_API_KEY\"\)\s*", "", src)
    src = re.sub(r"load_dotenv\(\)\s*", "", src)
    return src.strip() + "\n"


def needs_boot(nb: dict) -> bool:
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code" and "from src.llm import" in cell_text(cell):
            return False
    return True


def has_code(nb: dict) -> bool:
    return any(c.get("cell_type") == "code" and cell_text(c).strip() for c in nb.get("cells", []))


def process(path: Path) -> bool:
    nb = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    if has_code(nb) and needs_boot(nb):
        boot_cell = {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [BOOT],
        }
        # insert after leading markdown
        idx = 0
        cells = nb.get("cells", [])
        while idx < len(cells) and cells[idx].get("cell_type") == "markdown":
            idx += 1
        cells.insert(idx, boot_cell)
        changed = True
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        raw = cell_text(cell)
        if any(
            tok in raw
            for tok in (
                "initialize_agent",
                "ChatOpenAI",
                "OpenAIEmbeddings",
                "from langchain.llms import OpenAI",
                "from langchain.chat_models import",
                "OllamaLLM",
                "from langchain.llms import Ollama",
            )
        ):
            new = rewrite_code(raw)
            if "from src.llm import" not in new and "get_llm" in new:
                new = (
                    "from src.paths import ensure_sys_path, find_repo_root\n"
                    "ensure_sys_path(find_repo_root())\n"
                    "from src.llm import REPO_ROOT, get_agent, get_embeddings, get_llm\n"
                    + new
                )
            set_cell_text(cell, new)
            cell["outputs"] = []
            cell["execution_count"] = None
            changed = True
    if changed:
        path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def main() -> None:
    n = 0
    for path in sorted(ROOT.rglob("*.ipynb")):
        if any(part in SKIP_DIRS or part == ".ipynb_checkpoints" for part in path.parts):
            continue
        if process(path):
            print("updated", path.relative_to(ROOT).as_posix())
            n += 1
    print("updated_count", n)


if __name__ == "__main__":
    main()
