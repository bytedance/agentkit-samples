# Troubleshooting

Branch on `error.code`; do not parse message text when a stable code exists.

| Code | Action |
| --- | --- |
| `AUTH_REQUIRED` / `TOKEN_EXPIRED` / `REFRESH_FAILED` | Ask the user to run `setup_command` in their local terminal, then retry after confirmation. |
| `AUTH_REQUIRED` with `arkcli_status=state_snapshot_failed` | The Skill could not create its private arkcli state snapshot. Use the local hidden API-key prompt or repair read access to `~/.arkcli`. |
| `FORBIDDEN` | Report missing permission. |
| `VOLCENGINE_REAL_NAME_REQUIRED` | Do not treat this as an expired API key. Show `verification_url`, ask the user to complete real-name verification on Volcengine, then run `auth status` and retry the allocation. Existing allocated CUA invocations remain usable. |
| `VOLCENGINE_REAL_NAME_CHECK_UNAVAILABLE` | Retry the same read/status operation later. If the failed operation was about to allocate a new CUA, do not submit a duplicate request while status is unknown. |
| `DESKTOP_NOT_BOUND` | Report that no CUA desktop is provisioned. |
| `CONFIRMATION_REQUIRED` / `ConfirmationRequired` | Do not bypass confirmation. Run shutdown only after the user explicitly requests it, then include `--confirm`. |
| `IDEMPOTENCY_KEY_REQUIRED` / `IdempotencyKeyRequired` | Supply one stable unique key for the user-requested lifecycle action and reuse it for retries of that same action. |
| `DesktopRetentionExpired` / `DesktopNotRecoverable` | The exact retained desktop cannot be recovered. Do not silently omit its id and allocate a replacement; explain the state and ask whether the user wants a new desktop. |
| `DesktopRetentionCleanupPending` | Cleanup of an expired primary desktop is still in progress. Report it and retry start later only if the user still wants it. |
| `BillingAccessSuspended` / `AgentPlanSubscriptionInactive` | Starting would violate current billing or subscription eligibility. Report the condition; do not bypass it with a new allocation. |
| `IdempotencyConflict` | The key is already bound to a different start or shutdown request. Do not change the key to force the action; reconcile the original request first. |
| `ACTIVE_RUN_CONFLICT` | Stop; the new task did not start. Tell the user the desktop is busy. |
| `REVISION_CONFLICT` / `RevisionConflict` | The desktop changed before shutdown was accepted. Inspect current desktop state; do not submit a new shutdown without renewed user intent. |
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
| `TARGET_CAPABILITY_UNAVAILABLE` | The deployed AgentPlan manifest or exact target does not advertise all Credential capabilities. Stop; do not download/fallback/delegate. |
| `SOURCE_BROWSER_USER_ACTION_REQUIRED` | Relay the one-time Load unpacked instruction and exact directory from `error.message`, then rerun the same site-scoped request. This is the intentional cross-platform initial-install path; do not request macOS Accessibility permission, copy the Chrome Profile, extract Cookie/CDP state, or broaden to `--all`. |
| `DEPENDENCY_UNAVAILABLE` | The pinned official Credential Skill archive could not be fetched. Retry the same setup/sync later; do not use an unpinned mirror. |
| `DEPENDENCY_INVALID` | The repository, full commit pin, archive, permissions, or Target Adapter contract failed validation. Stop and repair the published skill. |
| `BROWSER_SETUP_REQUIRED` | The exact target Agent is ready but the browser extension/heartbeat is not. Complete browser installation only; do not open Options for per-site permission. |
| `BROWSER_PERMISSION_REQUIRED` / `HOST_PERMISSION_REQUIRED` | Chrome is withholding required HTTPS Site access for an exact signed Policy Origin. Keep the same Job and ask the user to restore Site access; do not request a per-site permission or create a new Job. |
| `BROWSER_NETWORK_UNREACHABLE` | Keep the same Job and follow its bounded network recovery path; never repeat Restore or expose the validation URL/proxy. |
| `INTERNAL` | Retry once; if it persists, report it. |

## Common situations

- Login is required: show `setup_command` and ask the user to run it in their local terminal. Never ask the user to paste a key into chat.
- A task appears stuck: continue watching while the outcome is `in_progress`.
- The desktop is busy: do not retry after `ACTIVE_RUN_CONFLICT` unless the user asks later.
- An artifact is missing or HTML: ask CUA to export a registered downloadable artifact.
- An output path already exists: select a new path; overwriting is intentionally unsupported.
- A new signed HTTPS Policy appears: no installation or per-site authorization step is needed. If it is not authorized, diagnose Chrome Site-access withholding or Policy rejection; never open Options or call a permission mutation.
