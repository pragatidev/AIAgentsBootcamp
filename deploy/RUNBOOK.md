# DataFlow on-call runbook

Health plus one POST. Not a four-cloud playbook.

## Who to call

On-call: the engineer who last deployed the dataflow image.
Escalation: the desk lead who can resume a parked refund.

## Health

GET /health

Expect `{"ok": true, "service": "dataflow"}`.

If health is 500, do not take tickets. Roll back. See the rollback row in
`deploy/second_tenant.md`.

## One POST

POST /run

Header `x-api-key`: the desk key from the environment.
Header `x-actor-id`: the reviewer when the ticket is a refund.

Body:

```
{"ticket": "Where is order DF-1002?"}
```

Expect a `thread_id` and a reply. A refund parks. Lookup does not.

## Rollback

If health fails after a deploy, retag the previous image and restart the
dataflow service. The rollback row names the image tag. Then hit health
and one POST again.

Do not open four clouds. This box is the default.
