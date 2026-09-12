# Second tenant

A second tenant is a second API key, not a second service. Add the key to
`DATAFLOW_API_KEYS` as `key:owner`. The door checks the key. The refund
tool reads the actor.

## Rollback row

| when | action | image tag |
| last bad deploy | retag previous and restart dataflow | dataflow-desk:previous |

The live tag is `dataflow-desk:live`. The previous known-good tag is
`dataflow-desk:previous`. A broken deploy that fails health is rolled back
by pointing live at previous.
