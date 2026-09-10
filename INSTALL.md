# Install

Python 3.11 or 3.12. VS Code. Git. **No API key.**

```
python -m venv .venv
```

Windows:

```
.venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

macOS / Linux:

```
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Open this folder in VS Code. Clone is done when `pytest -q` exits 0.

Copy `.env.sample` to `.env` and set a key, or use Ollama. Notebooks call `get_llm()`. Change `PREFERRED_PROVIDER` in `.env` to swap Anthropic, OpenAI, or Ollama. Do not edit the notebook to change models.

This folder is the repo root if you cloned `AIAgentsBootcamp`. If you opened it from inside another project, the first notebook cell still finds this folder.

First labs live in `labs/`. Live portfolios live in `Section_3_LangChain_GPT4` through `Section_9_LangGraph_Reliable_Workflows`. The product package is `northstar/`.

Optional live calls: copy `.env.sample` to `.env`. Set a key, or point `OLLAMA_BASE_URL` at a local server. Model ids are in `config.py`. Verify them at record time against `docs/CURRENCY.md`. Never commit `.env`.

Optional Docker is for S23. Clone and pytest do not start it.
