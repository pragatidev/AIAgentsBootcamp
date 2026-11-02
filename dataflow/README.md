# The DataFlow knowledge desk (RAG, Sections 22 to 25)

A support desk that answers from the DataFlow knowledge base with a citation, looks orders up without
searching, and refuses with one fixed sentence when nothing it retrieved survives the grader.

## Run it

Make and activate `.venv` as `INSTALL.md` says, pull the two local models (`ollama pull qwen3:8b` and
`ollama pull nomic-embed-text`), then run:

```
python labs/08_04_06_portfolio_knowledge_desk.py
```

The first run builds the index the desk reads, `dataflow/data/faiss_index_all/`, from every knowledge base
folder and the wiki; git ignores it. Every later run checks its `index_meta.json` and rebuilds or
refreshes it when a file or the embedder changed, so there is no separate build step.

## Tests

```
python -m pytest tests/test_rag_load_chunk.py tests/test_rag_index_tool.py tests/test_rag_graph.py tests/test_rag_cite_refuse_eval.py tests/test_lab_08_04_06.py tests/test_dataflow_rag_readme.py -q
```

None of them calls a model: they use `HashingEmbeddings` and `FakeChatModel` from `tests/fixtures/`, and
need no key and no Ollama.

## Design decisions

- One graph, `dataflow/graphs/rag_graph.py`: route, then retrieve, grade, rewrite once, and generate or
  refuse; an order id goes to lookup and never searches.
- The refusal is one fixed sentence, `REFUSE_TEMPLATE`, written by code, never by the model.
- A citation is the file plus its heading path or csv row, printed by `dataflow/rag/cite.py` from the
  passages the grader kept.
- Chunks are cut by heading (`dataflow/rag/chunk.py`), with the heading path written into each chunk.
- One embedder builds the index and embeds every question; `load_faiss_index` refuses a width mismatch.
- The scope is the deployment's choice, never the model's: this desk is `scope="all"`.

## Known limits

1. Scope: this desk is built with `scope="all"`, so it reads the internal folders and answers staff
   questions; it is a support-agent desk. The customer desk is `build_rag_graph()` with the default
   customer scope, which reads the wiki and the customer facing pages only.
2. Retrieved text is pasted into the grade and generate prompts as it is. The data box of Section 31 is
   one keyword away (`box_passages=True`) and ships off, and `dataflow/wiki/security.md` line 7 carries a
   planted instruction this index holds on purpose.
3. Dense search by default, no score threshold: the refusal comes from the grader emptying the set.
   Hybrid search and a rerank ship off (`retrieve_mode`, `rerank_enabled`).
4. The index is a FAISS file on one machine; `retrieve_store="pgvector"` reads the Section 23 Postgres.
5. Loading an index folder unpickles it (`allow_dangerous_deserialization=True`): load only folders you
   built.
6. The refusal names the rewritten question, which can read oddly to a customer.
7. The eval's judge is the desk's own model (`eval/runners/rag_metrics.py`).
8. The replies are the local model's words and differ from run to run.

## Sample run

On the build machine, 2026-11-02, qwen3:8b and nomic-embed-text on the local Ollama server, the desk's
first run:

```
model ChatOllama qwen3:8b
desk support_agent scope all
rebuilding_index all no index on disk yet
ticket policy-refund 'Who can approve a refund under 30 days?'
  route retrieve sources ['dataflow/knowledge_base/internal_operations/support_operations/customer_support_procedures.markdown'] refused False retrieved True
ticket refuse-coffee 'Do you sell coffee beans in the DataFlow shop?'
  route retrieve sources [] refused True retrieved True
ticket lookup-1002 'Where is order DF-1002?'
  route lookup sources [] refused False retrieved False
  Order DF-1002 is in_transit. Item: USB-C hub.
policy_cites_procedures True
unknown_refused True
order_route lookup
order_retrieved False
order_refused False
```

Your replies will be worded differently; the checks are what the tests hold.
