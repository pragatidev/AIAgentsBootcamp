# Strip AutoGen GPT-4 config, Langflow OpenAI-only steps, leftover GPT-4 instructions.
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MD_SWAPS = [
    ("Drag a **OpenAI** block onto the canvas and connect it to prompt block",
     "Drag a **Language Model** block (Anthropic, OpenAI, or Ollama — same provider as `.env`) and connect it to the prompt block"),
    ("Drag a **Chat Output** block and connect it to the OpenAI block",
     "Drag a **Chat Output** block and connect it to the language model block"),
    ("Langflow automatically routes your prompt to GPT-4 using the default OpenAI integration.",
     "Langflow routes your prompt to the model you configured in the Language Model block. Use the same provider as `.env`."),
    ("You’ll add **Chat Input**, connect it to a Prompt and OpenAI block, and route the result to a Chat Output.",
     "You’ll add **Chat Input**, connect it to a Prompt and a Language Model block, and route the result to a Chat Output."),
    ("4. Add an **OpenAI** block and paste your API key if required",
     "4. Add a **Language Model** block. Paste the key from `.env` (Anthropic, OpenAI, or Ollama)"),
    ("6. Connect Chat Input ➡ Prompt ➡ OpenAI ➡ Chat Output",
     "6. Connect Chat Input ➡ Prompt ➡ Language Model ➡ Chat Output"),
    ("   - `OpenAI`\n",
     "   - `Language Model` (same provider as `.env`)\n"),
    ("powered by GPT-4", "powered by the model from `.env`"),
    ("Uses GPT-4 to respond", "Uses the model from `.env` to respond"),
    ("to use GPT-4 as the brain", "to use the model from `.env` as the brain"),
    ("Configure the model (GPT-4) with your API key", "Configure the model from `.env`"),
    ("FAISS**, and **OpenAI Embeddings**", "FAISS**, and **local embeddings** (`get_embeddings()`)"),
    ("Ask GPT-4 Without RAG", "Ask the model without RAG"),
    ("how GPT-4 answers", "how the model answers"),
    ("feed that document contextually to GPT-4", "feed that document contextually to the model"),
    ("With RAG, GPT-4 has access", "With RAG, the model has access"),
    ("Use GPT-4 to generate", "Use `get_llm()` to generate"),
    ("powered by GPT-4, to simulate", "powered by `get_llm()`, to simulate"),
    ("- GPT-4 with LangChain\n", "- `get_llm()` with LangChain\n"),
]


def cell_text(cell: dict) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


def set_text(cell: dict, text: str) -> None:
    cell["source"] = [text] if text.endswith("\n") or "\n" not in text else (
        [line + "\n" for line in text.split("\n")[:-1]] + [text.split("\n")[-1]]
    )
    if not cell["source"]:
        cell["source"] = [text]


def main() -> None:
    n = 0
    for path in sorted(ROOT.rglob("*.ipynb")):
        if any(part in {".git", ".venv", ".ipynb_checkpoints"} for part in path.parts):
            continue
        nb = json.loads(path.read_text(encoding="utf-8"))
        ch = False
        for cell in nb.get("cells", []):
            text = cell_text(cell)
            new = text
            if "from src.llm import REPO_ROOT, get_agent, get_embeddings, get_llm" in new:
                new = new.replace(
                    "from src.llm import REPO_ROOT, get_agent, get_embeddings, get_llm",
                    "from src.llm import REPO_ROOT, get_agent, get_autogen_config, get_embeddings, get_llm",
                )
            if 'config_list = [{"model": "gpt-4", "api_key": openai_api_key}]' in new:
                new = new.replace(
                    'config_list = [{"model": "gpt-4", "api_key": openai_api_key}]',
                    "config_list = get_autogen_config()",
                )
            if 'openai_api_key = os.getenv("OPENAI_API_KEY")' in new and "AutoGen" in path.as_posix():
                new = (
                    "from src.llm import get_autogen_config, provider_name\n"
                    "print('provider', provider_name())\n"
                    "print('autogen_config_ready', bool(get_autogen_config()))\n"
                )
            if new.startswith("# Configure AutoGen with local Ollama"):
                new = (
                    "config_list = get_autogen_config()\n"
                    "llm_config = {\"config_list\": config_list, \"timeout\": 120}\n"
                    "print(\"AutoGen config from .env\", config_list[0].get(\"model\"), config_list[0].get(\"api_type\", \"openai-compat\"))\n"
                )
            if cell.get("cell_type") == "markdown":
                for a, b in MD_SWAPS:
                    if a in new:
                        new = new.replace(a, b)
            if new != text:
                set_text(cell, new)
                ch = True
        if ch:
            path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print("fixed", path.relative_to(ROOT).as_posix())
            n += 1
    print("fixed_count", n)


if __name__ == "__main__":
    main()
