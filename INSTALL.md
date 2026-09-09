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

First labs live in `labs/`. Open `labs/02_read_a_loop.py` and Run Cell. The product is `northstar/`.

Optional live calls: copy `.env.sample` to `.env`. Set a key, or point `OLLAMA_BASE_URL` at a local server. Model ids are in `config.py`. Verify them at record time against `docs/CURRENCY.md`. Never commit `.env`.

Optional Docker is for S23. Clone and pytest do not start it.
