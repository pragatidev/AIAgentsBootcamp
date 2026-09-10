# AI Agents Bootcamp workbench

Companion repo for the Udemy course **AI Agents Bootcamp** (listing 6521157).

One package (`northstar/`). One fake company. A support desk: a policy wiki, an order lookup, and an escalate-to-human gate. Models live in `config.py`, never in a lecture title.

[![pytest](https://img.shields.io/badge/pytest-no%20API%20key-2ea44f)](tests/test_smoke.py)
[![python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776ab)](.python-version)
[![license](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

## Quickstart

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

Live GitHub notebooks are back at the repo root: `Section_1_Introduction` through `Section_12_Bonus_Future_of_AI_Agents`, plus TalentFlow resumes and the DataFlow knowledge base. Those are the portfolios. `northstar/` and `labs/` are the 2026 spine growing beside them.

No cloud key is required for pytest. Hosted pings skip without a key. Local Ollama is the honest default. Copy `.env.sample` to `.env` if you want a key later. Never commit `.env`.

Notebooks call `get_llm()` from `src/llm.py`. Set `PREFERRED_PROVIDER` in `.env` to `anthropic`, `openai`, or `ollama`. Do not change the notebook to change the model. The first cell finds this repo whether you cloned it as the folder root or opened it from inside another project.

Course: https://www.udemy.com/course/ai-agents-bootcamp-build-with-langchain-rag-langflow-gpt/

## Layout

```
northstar/     the package you own by the end
labs/          S1-S8 teaching scripts (Run Cell on # %%)
config.py      the only place a model id lives
docs/CURRENCY.md
tests/         green without a key
```

No cloud key is required for pytest or for the S1-S8 labs except the hosted ping, which prints SKIPPED.

2025 notebooks from the live listing sit in `_archive/2025_live/`. They are not the path you follow.

`initialize_agent` does not ship.
