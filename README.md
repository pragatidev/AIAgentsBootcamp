# AI Agents Bootcamp, the 2025 edition (archived)

**This branch, `original-2025`, is the notebook edition of the course as it was before September 2026. It is archived and no longer updated.** The course was rebuilt, and the lectures on Udemy now teach from the branch `master`: one real repo with modules, tests, evals and a deploy door, because that is how agent products are built at work. Every lab there still comes with a notebook twin. If you started with these notebooks, they are all here, and every one of them runs top to bottom (checked from a fresh clone in September 2026). The lessons are the same. What changed is only what the new library versions needed: imports moved to `langchain_core`, `langchain_community` and `langchain_classic`, LangGraph states name their fields, a few cells that an earlier cleanup had overwritten are back, and `pip install -r requirements.txt -r requirements-archive.txt` adds the packages some notebooks import (crewai, langchain-openai, langchain-classic, groq, langchain-google-genai, jupyter).

`_archive/2025_live/` keeps a few old run outputs for reference. It is not the learner path; open the `Section_*` folders.

Companion repo for the Udemy course
https://www.udemy.com/course/ai-agents-bootcamp-build-with-langchain-rag-langflow-gpt/

Clone this folder. Open the notebooks in `Section_*` as the lectures tell you. Every notebook loads the model with `get_llm()` from `.env`. You do not paste a key into a cell.

## Setup

Python 3.11 or 3.12.

```
git clone https://github.com/pragatidev/AIAgentsBootcamp.git
cd AIAgentsBootcamp
python -m venv .venv
```

Windows:

```
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-archive.txt
copy .env.sample .env
pytest -q
```

macOS / Linux:

```
source .venv/bin/activate
pip install -r requirements.txt -r requirements-archive.txt
cp .env.sample .env
pytest -q
```

`pytest -q` must exit 0 with no cloud key.

Then edit `.env`. For learning, leave `PREFERRED_PROVIDER=ollama` and run `ollama pull llama3.2`. For Claude or GPT, paste the key and set `PREFERRED_PROVIDER` to `anthropic` or `openai`. Never commit `.env`.

Open the repo root in VS Code or Jupyter. If this folder sits inside another project, the first notebook cell still finds it.

## What you open in class

- `Section_1_Introduction` through `Section_12_Bonus_Future_of_AI_Agents`: the live lectures
- Portfolio notebooks: TechCorp IT chatbot, TalentFlow HR, DataFlow RAG, SupportFlow, LangGraph document pipeline
- `src/llm.py`: `get_llm()`, `get_embeddings()`, `get_autogen_config()`
- `src/paths.py`: finds this repo at clone-root or nested
- `labs/` and `northstar/`: the 2026 package growing beside the live notebooks

## Layout

```
Section_1_Introduction/ ... Section_12_...
Section_5_Autonomous_Workflows/data/resumes/
Section_6_Real_World_RAG_Engineering/enterprise_knowledge_base/
src/llm.py
.env.sample
labs/
northstar/
tests/
```

Course id 6521157. License MIT.
