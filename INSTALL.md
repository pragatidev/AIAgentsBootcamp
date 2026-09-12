# Install

Python 3.11 or 3.12. VS Code. Git. No API key.

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

- leave it on Ollama (default) and run `ollama pull qwen3:8b`. No key. This is the student default in `config.py`.
- set `OPENAI_API_KEY` and `OPENAI_CHAT_MODEL`.
- set `ANTHROPIC_API_KEY` and `ANTHROPIC_CHAT_MODEL`.

Labs call `get_chat_model()` in `config.py`. Do not paste keys into cells. Do not commit `.env`.

This folder is the repo root when you clone `AIAgentsBootcamp`.

First labs live in `labs/`. The three worlds are `techcorp/`, `dataflow/`, and `talentflow/`. 2025 listing notebooks sit in `_archive/2025_live/` and are not the path you follow.

Optional Docker is for later deploy labs. Clone and pytest do not start it.
