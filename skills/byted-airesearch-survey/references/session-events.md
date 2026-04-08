# Session Events

Use this file when processing tool responses that contain `session_event`.

## Source of truth

Session events come from two sources:
- **Client-generated**: Produced by the tool itself during auth flow, local queries, or error handling. These never reach the backend.
- **Backend-generated**: Produced by the backend during plan creation, revision, confirmation, and execution. These pass through the tool unchanged.

The host does not need to distinguish between the two sources. Treat all events as opaque rendering hints.

## Client-generated events

| Value | Meaning | Host action |
|-------|---------|-------------|
| `pending_request_saved` | No credential available. The research request has been saved locally and will replay after the user provides an API key. | Show the auth prompt from `reply_markdown`. Do not ask the user to repeat their request. |
| `pending_request_waiting_auth` | A pending request already exists. Still waiting for API key. | Show the auth prompt. The original request is preserved. |
| `pending_request_replayed` | A previously saved request was replayed with the newly provided credential. | Present the backend result normally. The replay is transparent to the user. |
| `auth_invalid` | The provided API key was rejected by the backend (HTTP 401). | Show the re-auth prompt from `reply_markdown`. Do not retry with the same key. |
| `local_query_only` | Response produced locally (version query, industry list) without contacting the backend. | Present `reply_markdown` as-is. No session state was changed. |
| `debug_query_only` | Redacted debug snapshot produced locally. Only when `debug_mode` was enabled. | Present the debug info from `reply_markdown`. |
| `request_failed` | Backend request failed due to transport or server error. | Present the error message from `reply_markdown`. Do not diagnose. |
| `business_error` | Backend returned a business-level error (e.g., rate limit, quota exceeded). | Present `reply_markdown` directly. The message is already user-safe. |

## Backend-generated events

| Value | Meaning | Host action |
|-------|---------|-------------|
| `created_new_plan` | A new research plan was created for this session. | Present the plan card from `reply_markdown`. Follow `next_actions`. |
| `deferred_generation_started` | Plan generation started in background (async mode). | Tell the user the plan is being generated. Follow `next_actions` for progress query options. |
| `restarted_after_stale_generating` | An old GENERATING plan timed out; a new plan was created. | Present the new plan. The timeout is transparent to the user. |
| `restarted_after_failed_plan` | User restarted from a FAILED plan. New plan created. | Present the new plan normally. |
| `restarted_after_finished_plan` | User started a new round after a FINISHED plan. | Present the new plan normally. |
| `queried_existing_plan` | User queried an existing plan (status, result, plan view). | Present the current plan state from `reply_markdown`. |
| `ignored_non_restart_on_terminal_plan` | User sent a non-restart message on a FINISHED/FAILED plan. | Present the current terminal state. Suggest restart via `next_actions` if available. |
| `confirmed_and_started_execution` | User confirmed the plan and execution was kicked off. | Present the confirmation. Follow `next_actions` for progress tracking. |
| `confirmed_existing_plan` | User confirmed the plan but execution not yet started. | Present the confirmation from `reply_markdown`. |
| `started_confirmed_plan_execution` | Execution started on an already-confirmed plan. | Present execution status from `reply_markdown`. |
| `deferred_revision_started` | Plan revision started in background (async mode). | Tell the user the revision is in progress. |
| `revised_existing_plan` | Plan was revised synchronously based on user feedback. | Present the updated plan card. Follow `next_actions`. |
| `new_request_from_waiting_confirm` | User sent a new research request while a plan was waiting for confirmation. | Present the new plan. |
| `new_request_from_waiting_confirm_deferred` | Same as above, but plan generation is async. | Tell the user the new plan is being generated. |
| `blocked_by_invalid_industry_hint` | The `industry_hint` parameter didn't match any supported industry. | Present the unsupported-industry message. Show supported industries. |
| `status_only` | Response from a status-only query (GET /status). | Present the current status from `reply_markdown`. |
| `""` (empty) | Normal response with no special lifecycle event. | Present `reply_markdown` and follow `next_actions`. |

## Rules

1. The host must not fabricate session event values not listed above.
2. The host must not expose `session_event` values directly to the user — they are rendering hints for the host, not user-facing labels.
3. When `session_event` indicates an auth flow (`pending_request_saved`, `pending_request_waiting_auth`, `auth_invalid`), the host must present the auth prompt and wait — do not attempt alternative call paths.
4. When `session_event` indicates a deferred operation (`deferred_generation_started`, `deferred_revision_started`), inform the user that processing is in progress and suggest using `next_actions` to check back later.
