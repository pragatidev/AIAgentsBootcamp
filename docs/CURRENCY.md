# Currency. Verify at record time.

Nothing in this file is a promise that the id still exists tomorrow. Before a screen walk that prints a model name, open the provider console or `ollama list` and copy what is live into `config.py`.

Never put a model id in a lecture title.

## Local default

- Runtime: Ollama at `http://localhost:11434/v1`
- Chat tag to verify: `llama3.2:3b` (also acceptable if present: `llama3.2:1b`, `qwen2.5:3b`)
- No key.

## Cloud (empty until a live lab)

Set the env var, then the id in `config.py`. Confirm the id in the vendor console the day you record.

- OpenAI chat: `OPENAI_CHAT_MODEL` (COURSE_DESIGN candidates included GPT-5.6 family and GPT-6 Astra. Confirm, do not guess.)
- Anthropic chat: `ANTHROPIC_CHAT_MODEL` (COURSE_DESIGN candidates included Claude Fable 5.1 and Opus 5. Confirm, do not guess.)

If the record machine has no key and the lecture needs a live call, HALT. Do not invent stdout.

## APIs that move

Verify these the week you record the matching lab:

- LangGraph interrupt, checkpointer, store
- MCP SDK and transports
- LangSmith vs a local tracer
- Docker base image for S23

Re-run the factory every 3-6 months. Re-record a screen walk when the UI changed.
