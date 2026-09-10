# Install

Python 3.11 or 3.12. VS Code or Jupyter. Git.

```
python -m venv .venv
```

Windows:

```
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.sample .env
pytest -q
```

macOS / Linux:

```
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
pytest -q
```

Clone is done when `pytest -q` exits 0 with no cloud key.

Open `.env`. Pick one:

- `PREFERRED_PROVIDER=ollama` — install [Ollama](https://ollama.com), then `ollama pull llama3.2`. No key.
- `PREFERRED_PROVIDER=anthropic` — set `ANTHROPIC_API_KEY`.
- `PREFERRED_PROVIDER=openai` — set `OPENAI_API_KEY`.

Notebooks call `get_llm()` in `src/llm.py`. AutoGen calls `get_autogen_config()`. Langflow: use a Language Model block with the same provider. Do not paste keys into cells. Do not commit `.env`.

This folder is the repo root when you clone `AIAgentsBootcamp`. If you opened it from inside another project, the first notebook cell still finds this folder.

Live lectures are `Section_1_Introduction` through `Section_12_Bonus_Future_of_AI_Agents`. Portfolios sit in those section folders. `labs/` and `northstar/` are extra 2026 code beside them.
