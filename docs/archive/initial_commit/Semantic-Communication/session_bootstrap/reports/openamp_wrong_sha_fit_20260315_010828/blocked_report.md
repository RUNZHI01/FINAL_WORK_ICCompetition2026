# OpenAMP FIT-01 blocked report

- generated_at: `2026-03-15T01:09:03+0800`
- status: `BLOCKED`
- blocker_kind: `ssh_connect_failed`
- host: `100.121.87.73:22`

## Exact blocker

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

## Meaning

The run stopped before any board-side `STATUS_REQ` or `JOB_REQ` was sent. This is a workspace network restriction, not a firmware decision.

## Next step

Re-run `session_bootstrap/scripts/run_openamp_fit_wrong_sha.py` from an execution context that can open outbound SSH sockets to the Phytium Pi.
