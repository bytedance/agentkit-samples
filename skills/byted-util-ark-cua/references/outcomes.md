# Outcome state machine

Delegation and task commands return an envelope under `data`:

```json
{
  "invocation_id": "cua_inv_...",
  "outcome": "in_progress | needs_input | completed | failed | cancelled",
  "result": {"text": null, "artifacts": []},
  "input_request": {"question": "...", "choices": []},
  "progress": {"summary": "..."},
  "next_action": {"agent_hint": "..."}
}
```

## Transitions

```text
delegate -> in_progress -> watch -> in_progress
                              |----> needs_input -> answer -> in_progress
                              |----> completed
                              |----> failed
                              `----> cancelled
```

## Handling rules

| Outcome | Action |
| --- | --- |
| `in_progress` | Run `next.command`; do not answer from progress text. |
| `needs_input` | Relay the question verbatim and submit the user's reply. |
| `completed` | Use `result.text` as the authoritative final result. |
| `failed` | Explain the failure; retry only when requested and safe. |
| `cancelled` | Report cancellation. |

A timeout is not an outcome. Continue the same invocation after retryable gateway or transport errors. Never create a duplicate task.

`ACTIVE_RUN_CONFLICT` means the new request was rejected before task creation. Stop and tell the user that the desktop is busy.
