# AI Agents Bootcamp workbench

Companion repo for the Udemy course AI Agents Bootcamp (listing 6521157).

**Which branch do I need?** The course was rebuilt in September 2026, and the branch you are reading is the rebuilt course: every lecture names a file under `labs/`, and each lab comes as a plain `.py` script and an `.ipynb` twin, so you can work in an editor or in a notebook. It is written as a real repo on purpose, because that is how agent products are built at work: modules, tests, config, evals and a deploy door, not one long notebook. Took the 2025 edition? Your notebooks are on the branch `original-2025`, exactly as you had them: `git fetch && git checkout original-2025`. That branch is archived and no longer updated.

Three builds:

- DataFlow desk: a LangGraph support desk with retrieve, a parked refund, citations, and a refuse line.
- Research and report agent: a plan, files, isolated subagents, and a sourced report on disk.
- TalentFlow pipeline: map-reduce over resumes, a job description, and email templates.

Four files a clone needs: README (this file), smoke (`deploy/smoke.py`), golden set (`eval/golden.jsonl`), the FastAPI door (`dataflow/serve/app.py`).

## Clone and test (no key)

```
git clone https://github.com/pragatidev/AIAgentsBootcamp.git
cd AIAgentsBootcamp
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

Use Python 3.13 from python.org's standalone installer; 3.11 and 3.12 also work, but python.org no longer gives them regular bug fixes or binary installers. The Python docs (read 2026-10-04) recommend the Python install manager and mark the classic installer and the classic `py` launcher as deprecated since 3.14. If PowerShell says `Activate.ps1 cannot be loaded because running scripts is disabled on this system`, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once (the fix the Python venv docs give) and activate again, or use cmd. On our test machine with a warm pip cache the install took 247.2 seconds and 1.82 GB on Python 3.13 (278.8 seconds and 1.9 GB on 3.11), and a first install downloads everything, so expect it to take longer; PyTorch comes in through `sentence-transformers`. macOS / Linux: `python3 -m venv .venv` and `source .venv/bin/activate`. `pytest -q` must exit 0 with no cloud key and print the `N passed` line. Copy `.env.sample` to `.env` (`copy` on Windows, `cp` on macOS / Linux) when you add a key or change a model. Live model calls skip without a key or Ollama. The browser labs (Playwright) need a browser that pip does not install: run `playwright install chromium` once; until then their eight tests skip and say so. Full steps: `INSTALL.md`. Errors and fixes: `TROUBLESHOOTING.md`.

## What the desk refuses

The DataFlow desk refuses when the knowledge base has nothing. It does not invent a policy. It does not write a refund until a named reviewer resumes the parked card.

For labs that call a model, install Ollama and run `ollama pull qwen3:8b`. Models live in `config.py`. Never commit `.env`. Capstones: `labs/19_dataflow/starter`, `labs/19_research/starter`, `labs/19_talentflow/starter`.
Part 16 compares agent frameworks: run `pip install -r requirements-frameworks.txt` once (CrewAI and AutoGen get their own venv, the steps are in that file).

## Layout

```
techcorp/           IT desk (LangChain)
dataflow/           customer desk, graphs, RAG, MCP, FastAPI
talentflow/         resumes, job, email templates
research_agent/     research and report package
eval/golden.jsonl   golden set
deploy/smoke.py     clone smoke
labs/               teaching scripts plus .ipynb twins
tests/              green without a key
config.py           the only place a model id lives
src/                the model door (llm.py), the repo finder (paths.py), helpers the Section 2 labs use
harness/            the DataFlow harness: guides, sensors, permissions, and recorded runs
scripts/            repo tools, such as make_twins.py, which rebuilds the notebook twins
evals/              one line that points to eval/harness.py
exercises/          a starter for one coding exercise (an unknown order id)
solutions/          the solution to that exercise
prompts/            the DataFlow system prompt
business/           a DataFlow offer and price, and TalentFlow versus a recruiting ATS
career/             PM pages (spec, metrics, cost model) and a QA test plan for DataFlow
docs/               CURRENCY.md: check that a model id is live before you use it
ops/                tracing/runs/, where the DataFlow service writes its request log
.github/            a workflow that runs the eval gate on every pull request
conftest.py         keeps pytest out of the lab scripts
```

## RAG (Part 8)

Local default embedder is `nomic-embed-text` on Ollama. Chat is `qwen3:8b`.

```
python -m dataflow.rag.faiss_index                 # build the FAISS index (dataflow/data/faiss_index, gitignored)
python labs/08_04_06_portfolio_knowledge_desk.py   # three tickets: a cited policy, an unknown that refuses, an order id that does not retrieve
python labs/08_04_05_rag_evals.py                  # naive vs agentic evals on eval/questions.jsonl
```

First lab: `labs/00_03_setup_check.py`. Twins: `python scripts/make_twins.py`. License MIT.
