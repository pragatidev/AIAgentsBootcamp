# eval/questions.jsonl: why each row is there

A JSONL file cannot hold comments, so the selection method lives here. The file is the twelve questions
Section 25 scores (`eval/runners/rag_metrics.py`) and Section 26 uploads as a dataset. Section 28 grows
the 21-row golden set (`eval/golden.jsonl`) from it.

## The twelve rows

| id | kind | why it is there | expected_source |
|---|---|---|---|
| policy-return | policy | a wiki markdown page answers it | dataflow/wiki/return_policy.md |
| policy-shipping | policy | a second wiki page | dataflow/wiki/shipping.md |
| policy-billing | policy | a csv row answers it, so the citation must name the row | dataflow/knowledge_base/business_data/billing_and_pricing.csv |
| policy-refund | policy | an internal markdown file answers it (only the support-agent scope can) | dataflow/knowledge_base/internal_operations/support_operations/customer_support_procedures.markdown |
| lookup-1001 | lookup | an order id goes to the order lookup, never to retrieve | none |
| lookup-1002 | lookup | the same, a second status | none |
| refuse-student | refuse | the corpus does not answer it; the id was kept when its question changed to the lifetime lamp warranty | none |
| refuse-coffee | refuse | the corpus does not answer it | none |
| refuse-gym | refuse | the corpus does not answer it | none |
| paraphrase-lamp | paraphrase | the return question in other words (the near miss of 23.1) | dataflow/wiki/return_policy.md |
| paraphrase-p0 | paraphrase | a P0 question in other words | dataflow/knowledge_base/internal_operations/support_operations/customer_support_procedures.markdown |
| paraphrase-ship | paraphrase | the shipping question in other words | dataflow/wiki/shipping.md |

One row per answer-bearing file type and scope (wiki markdown, a csv row, internal markdown), a paraphrase
twin per policy, refuse rows for asks the corpus does not answer, lookup rows for the order route. Each
expected source was checked by a person opening the file.

## What each metric counts

`context_recall` (in `score_row`) is 1 when the expected file is among the sources or the retrieved
passages, and 1 by definition on the five rows with no expected file (three refuse, two lookup). Section
29's floors gate on it as it is, so it is not redefined. `retrieval_metrics` scores only the seven rows
that name a file: the rank of that file in the top passages, recall at 1, 3 and 5, and MRR, with no chat
model. With seven scored rows one row moves a recall by 1/7, about 0.14.

## How an enterprise grows this file

1. Sample from real tickets, stratified by route. `dataflow/data/tickets.jsonl` holds 30 tickets,
   T-3001 to T-3030, with no expected outcome: labelling them is the exercise.
2. A person labels the expected source and the expected outcome (answer, lookup, refuse).
3. Freeze the file and version it; a changed row is a commit with a reason.
4. Every production miss becomes a row (Section 21: a miss becomes a test).

No target size is set here. The arithmetic that sets one: with the 21 golden rows one row moves a mean by
1/21, about 0.048, which is more than the 0.04 maximum drop `eval/thresholds.toml` allows for
faithfulness and context_recall, so one flipped row can fail that gate. That is a fact for Section 29's
owner of the floors.
