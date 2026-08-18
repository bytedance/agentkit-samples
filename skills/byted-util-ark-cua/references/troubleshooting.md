# Troubleshooting

Branch on `error.code`; do not parse message text when a stable code exists.

| Code | Action |
| --- | --- |
| `AUTH_REQUIRED` / `TOKEN_EXPIRED` / `REFRESH_FAILED` | Ask the user to run `setup_command` in their local terminal, then retry after confirmation. |
| `AUTH_REQUIRED` with `arkcli_status=state_snapshot_failed` | The Skill could not create its private arkcli state snapshot. Use the local hidden API-key prompt or repair read access to `~/.arkcli`. |
| `FORBIDDEN` | Report missing permission. |
| `DESKTOP_NOT_BOUND` | Report that no CUA desktop is provisioned. |
| `ACTIVE_RUN_CONFLICT` | Stop; the new task did not start. Tell the user the desktop is busy. |
| `runtime_capability_required` | Revoke the failed desktop ticket and run `desktop access` once for a new URL. Do not rewrite the URL. If the new URL also fails, report a Desktop Gateway/runtime configuration problem. |
| `INVOCATION_NOT_FOUND` | Recheck the ID or use `--last`; never guess. |
| `INVOCATION_NOT_WAITING_INPUT` | Check task status before answering. |
| `CONTEXT_NOT_FOUND` | Use `context list` or the exact context ID. |
| `ARTIFACT_NOT_FOUND` | Recheck `artifact list`; a placeholder may have no bytes. |
| `PAYLOAD_TOO_LARGE` | Shorten task input or use an artifact smaller than 256 MiB. |
| `MODEL_TIMEOUT` | Report the safe reason and request ID; retry only when requested. |
| `DESKTOP_UNHEALTHY` / `SESSION_CLEANUP` / `UPSTREAM_FAILURE` | Report safe diagnostic fields; do not retry blindly. |
| `GATEWAY_TIMEOUT` / `CUA_BACKEND_UNAVAILABLE` / `RATE_LIMITED` / `NETWORK` | Retry the same watch/status/result operation; do not create a duplicate task. |
| `VALIDATION_ERROR` | Correct the indicated argument or choose a new output path. |
| `INTERNAL` | Retry once; if it persists, report it. |

## Common situations

- Login is required: show `setup_command` and ask the user to run it in their local terminal. Never ask the user to paste a key into chat.
- A task appears stuck: continue watching while the outcome is `in_progress`.
- The desktop is busy: do not retry after `ACTIVE_RUN_CONFLICT` unless the user asks later.
- An artifact is missing or HTML: ask CUA to export a registered downloadable artifact.
- An output path already exists: select a new path; overwriting is intentionally unsupported.
