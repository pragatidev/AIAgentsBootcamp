# Install

Python 3.13. VS Code. Git. No API key.

## Python

Install Python 3.13, the version in `.python-version`, with the standalone installer from python.org. On
python.org/downloads/windows/ that is "Python 3.13.16 - Sept. 30, 2026" with "Download Windows installer (64-bit)", and
on python.org/downloads/macos/ the same release has "Download macOS installer" (both read on 2026-10-04). The tests pass
on 3.13.

Python 3.11 and 3.12 also work. For a new install, pick 3.13: python.org says 3.11 and 3.12 each "isn't receiving
regular bug fixes anymore, and binary installers are no longer provided for it".

The Python docs (Using Python on Windows, read on 2026-10-04) recommend the Python install manager, from
python.org/downloads or the Microsoft Store, and mark the classic full installer and the classic `py` launcher as
deprecated since Python 3.14. The full installer will not be made for 3.16 or later. Check which versions you have with
`py --list`.

## Get the code

```
git clone https://github.com/pragatidev/AIAgentsBootcamp.git
cd AIAgentsBootcamp
```

## Make the virtual environment and install

Windows (PowerShell or cmd):

```
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.sample .env
pytest -q
```

macOS / Linux:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
pytest -q
```

If PowerShell stops at the activate line with this error:

```
& : File ...\.venv\Scripts\Activate.ps1 cannot be loaded because running scripts
is disabled on this system.
```

run this once, as the Python venv docs give it, then activate again:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Or use cmd, where `.venv\Scripts\activate` runs `activate.bat` and needs no policy change.

The install is big and slow. On our Windows test machine `pip install -r requirements.txt` took 278.8 seconds (about
4.6 minutes) with most packages already in pip's cache, and `.venv` came to 1.9 GB. A first install downloads
everything, so expect it to take longer. It includes PyTorch (the CPU build, a 118 MiB wheel), which you do not
install by name: it arrives because `sentence-transformers` needs it.

Clone is done when `pytest -q` exits 0 with no cloud key and its last line counts the tests, like
`N passed, N skipped`. Confirm it yourself with `python labs/00_03_setup_check.py`: it exits with pytest's code and its
last line starts with `GREEN` or `NOT GREEN`. If something fails, look the error up in `TROUBLESHOOTING.md`.

## Pick a model

Open `.env`. Pick one:

- leave it on Ollama (default) and run `ollama pull qwen3:8b` (5.2 GB). No key. This is the student default in `config.py`.
- set `OPENAI_API_KEY` and `OPENAI_CHAT_MODEL`.
- set `ANTHROPIC_API_KEY` and `ANTHROPIC_CHAT_MODEL`.

Set the key and its model id together. With a key and no model id, `config.py` prints a warning and uses the local
model.

Labs call `get_chat_model()` in `config.py`. Do not paste keys into cells. Do not commit `.env`.

This folder is the repo root when you clone `AIAgentsBootcamp`.

First labs live in `labs/00_03_setup_check.py`, `labs/00_04_keys_and_config.py`, and `labs/00_05_notebook_twin_demo.py`. The three worlds are `techcorp/`, `dataflow/`, and `talentflow/`. The 2025 edition notebooks are not in this branch; they live on the branch `original-2025` (`git checkout original-2025`), archived as they were.

Later labs also use `llama3.2:3b` (2.0 GB, model swap) and `nomic-embed-text` (274 MB, similarity recall). Pull them when those lectures say so:

```
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

All three models plus `.venv` come to about 9.5 GB of disk.

Optional Docker is for later deploy labs. Clone and pytest do not start it.
