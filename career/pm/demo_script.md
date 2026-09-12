# DataFlow stakeholder demo (five minutes)

Run from the course repo root with the service up (scripts/serve_dataflow.py) and the model from config.py. Tickets match deploy/smoke.py.

Minute 1. Open career/pm/spec.md. Read the job sentence, the four tools with read or write, the three stops, the gate with reviewer-1, and done-when as eval/golden.jsonl.

Minute 2. Lookup POST to /run. Ticket: Where is order DF-1002? Tracking still says in transit. Show the reply and the thread_id. This is a read. It must not park.

Minute 3. Refuse POST to /run. Ticket: Do you sell coffee beans in the DataFlow shop? Leave the refuse on screen. A demo that skips this POST hides the desk saying no, and the stakeholder leaves thinking it always answers.

Minute 4. Park POST to /run. Ticket: Please refund order DF-1001. The desk lamp is unused. Show the park payload. issue_refund waited. reviewer-1 has not resumed yet. No ledger row.

Minute 5. Open ops/cost_report.md. Read the cost line: tokens, milliseconds, model id. No money column. That is the envelope from career/pm/cost_model.md.

Done when the spec, the refuse, the park payload, and the cost line have all been on screen.
