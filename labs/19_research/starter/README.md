# Research and report agent starter

A long job over many DataFlow files: a plan, a filesystem, isolated reader subagents, and a report on disk with a Sources section.

Fill the TODO bodies in `agent.py` (plan, files, isolated subagents). `write_report` runs, but this starter writes a report with no sources. That is the plant. Add a citation check. An empty-source run must fail it. Then write a sourced report.

## Test with no key

From the course repo root:

```
pytest labs/19_research/starter/check -q
```

## Sample

`reports/sample.md` is the shape a clone should see: themes plus a Sources section with real paths.

The model comes from course `config.py` (`qwen3:8b` on Ollama by default).
