# DataFlow desk capstone starter

A hiring manager clones this folder, runs the tests, and reads the refuse line.

Fill the TODO node bodies in `graph.py` (classify, lookup, generate, refuse). Retrieve is already wired. The refund parks before any write. The tracer is wired.

Four files a clone needs in this starter:

- README (this file)
- smoke (`smoke.py`)
- golden set (`golden.jsonl`, eight rows)
- the FastAPI door (`app.py`)

## Test with no key

From the course repo root:

```
pytest labs/19_dataflow/starter/check -q
```

`pytest -q` on the course tests must still exit 0 with no cloud key.

## What the desk refuses

The DataFlow desk refuses when the knowledge base has nothing. It does not invent a policy. It does not write a refund until a named reviewer resumes the parked card.

This starter has no refuse test. Add one. A fluent miss that says yes to coffee beans should fail that test.

Smoke (fixture model, no live port): `python smoke.py`. Models live in course `config.py`.
