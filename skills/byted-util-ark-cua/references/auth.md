# Auth

This AgentPlan CUA skill uses the caller's Volcengine Ark AgentPlan API key as
the bearer credential. The gateway validates that key with Ark acquire, resolves
an AgentPlan-only user principal, allocates the user's cloud desktop, and passes
the same API key to CUA runtime model calls.

## Login

1. A business command (or `auth status`) reuses the protected local credential
   when present. Otherwise it checks whether `arkcli` is in `PATH`.
2. If arkcli is installed, the CLI copies only `config.yaml`, legacy
   `profile.yaml` / `.env`, and the `identities` / `identity_store` directories
   into a private `0700` temporary HOME. It runs
   `arkcli profile list --format json` there and selects the first profile whose
   `type` is exactly `agent-plan` and whose `plan_tier` is exactly `max`. Arkcli
   then brokers the selected profile credential into a redacted, non-serializable
   handle. The real arkcli state is not modified, and the temporary snapshot is
   deleted after discovery.
3. An arkcli-sourced credential is validated through `/v1/auth/me`, used only in
   that process, and never copied into the CUA cache. Successful auth output
   exposes only its source and selected profile metadata. For AgentPlan users it
   also reports `real_name_verification`. An unverified result does not make the
   API key invalid and does not interrupt an already allocated CUA; it prevents
   only a later operation that must allocate a new CUA.
4. If arkcli is not installed, has no personal Agent Plan Max profile, has no
   usable key, or otherwise fails, `AUTH_REQUIRED` includes `arkcli_status`,
   `arkcli_hint`, and the existing `setup_command`. Ask the user to run that
   command in their own local terminal; it uses the hidden API-key prompt.

### Explicit manual login

When the user intentionally needs a different account or machine credential,
even while arkcli is installed and valid, ask them to run this in their own
local terminal:

```bash
python3 scripts/cua.py auth login --manual
```

`--manual` skips arkcli discovery for that login only and reads the API key
through `getpass`, so it is not echoed or passed as a command argument. After
gateway validation, the key is stored in the same protected `0600` cache.
Business commands already prefer that cache over arkcli, so the manual identity
remains active until `auth logout` clears it. Normal `auth login`, `auth status`,
and business-command discovery keep their existing behavior when no manual key
is cached. If a cached manual key is rejected, the CLI returns the manual login
command instead of falling back to arkcli, avoiding an unintended identity or
desktop switch. `--manual` and `--no-prompt` are mutually exclusive.

When stdin is not a TTY, `auth login` does not prompt or block. It returns
`AUTH_REQUIRED` with `setup_command` so the agent can ask the user to perform the
login in a real local terminal instead of pasting the API key into chat.

## Local Cache

- Location: `~/.openclaw/ark-cua/auth.json` (override with
  `AP_CUA_SKILL_AUTH_FILE`).
- Permissions: `0600`; the script attempts to repair unsafe permissions and
  refuses to continue if it cannot.
- `auth.json` holds the API base URL and, only for the hidden local-prompt
  fallback or explicit `--manual` login, the protected credential plus its
  source, last verified user summary, and desktop binding flag. Arkcli-sourced
  keys are never copied here. Cache contents are never printed.

## Auth Errors

| Error | Meaning | Action |
| --- | --- | --- |
| `AUTH_REQUIRED` | no usable key from existing configuration or arkcli, or the key is invalid | inspect `arkcli_status`; fix arkcli when practical, otherwise ask the user to run fallback `setup_command`, then retry |
| `AUTH_REQUIRED` with `arkcli_status=state_snapshot_failed` | arkcli state could not be copied into a private temporary HOME | use the local hidden API-key prompt or fix access to the user's arkcli state |
| `AUTH_REQUIRED` with `manual_login_required=true` | the explicit manual path needs a real local TTY, or the manual key was rejected | run `setup_command` in the user's local terminal and enter the key through the hidden prompt; never paste it into chat |
| `TOKEN_EXPIRED` | gateway rejected the bearer credential | ask the user to run `setup_command` in their own local terminal again |
| `REFRESH_FAILED` | legacy alias for re-login needed | ask the user to run `setup_command` in their own local terminal again |
| `FORBIDDEN` | API key is valid but not allowed for this operation | do not retry with the same key |
| `VOLCENGINE_REAL_NAME_REQUIRED` | API key is valid, but the account has not completed Volcengine real-name verification and this operation would allocate a new CUA | show `verification_url`, ask the user to complete verification on Volcengine, then rerun `auth status` and retry the allocation |
| `VOLCENGINE_REAL_NAME_CHECK_UNAVAILABLE` | the server could not determine verification state while a new CUA allocation was required | retry later; do not create a duplicate task |

## Logout

`auth logout` clears the local cache. There is no server-side refresh token to
revoke in this AgentPlan variant.
