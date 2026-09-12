# Research and report agent

A Deep Agents package that reads the DataFlow knowledge base and writes a sourced report. It imports DataFlow tools and files. It is its own portfolio repo.

It is a LangGraph agent from `create_deep_agent`: a todo plan in state, file tools over a backend, and an isolated `reader` subagent. That is the shape for a long job over many sources. It is not the support desk.

## How to run

From the course repo root, with Ollama serving `qwen3:8b`:

```
python -m research_agent "What are the main reasons customers ask for returns or refunds, and which policy lines apply? Write a short report with sources."
```

The real-folder backend writes under `research_agent/reports/`. The process prints `report_path` when a report file exists.

Labs:

- `labs/06_11_02_create_deep_agent.py` virtual filesystem, stream events, print todos and files
- `labs/06_11_03_filesystem_and_todo.py` real folder, print the todo list as it changes
- `labs/06_11_05_portfolio_research_agent.py` `python -m research_agent` then pytest

## When to use it

Ask four questions about the job. This is the same test as lecture 17.4.

1. Do you know the steps in advance? A ticket, yes: classify, look up, reply. A research question, no: which documents matter depends on what the first ones say. Known steps want a drawn graph. Unknown steps want a plan.
2. How many sources? One or two, a drawn graph with tools. Many, and the number changes with the job, a deep agent with subagents.
3. Does the job need notes that outlive a step? A ticket carries its state on the clipboard. A report needs a draft and a source list that grow over an hour. Notes across steps want files.
4. Is there a fixed approval path? A refund has one, and it must be a gate you can point at. A report has none; the human reads it at the end. A fixed path wants a drawn graph with an interrupt in a known place.

Four ticks on the desk side, keep the DataFlow graph. Four ticks on the research side, use this agent. When a ticket needs research, the desk stays the supervisor and this agent is a specialist behind the gate, not the desk itself.

A ticket does not need a plan. A three step job does not need files. A question answered from one document does not need a subagent.

## Sample report

`research_agent/reports/sample_return_complaints.md` is a real run copied after the lab, not a hand-written demo.

Runtime reports (`return_complaints.md`, `shipping_delays.md`, `notes.md`) are gitignored. They come back when you run the agent.

## Local model quality

Student default is `qwen3:8b` through `config.get_chat_model()`. A deep agent on an 8B local model may plan badly, skip `write_todos`, skip the reader subagent, or never write the report. That is a model limit, not a broken install. The labs print what the run actually did. Pytest stays green with a fixture model and no key.
