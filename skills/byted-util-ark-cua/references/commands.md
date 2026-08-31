# AgentPlan CUA Skill commands

All commands: `python3 <skill_dir>/scripts/cua.py <command> [options]`.
Global options precede the command. `--api-base-url <url>` overrides the gateway URL for one local-development call.
Gateway URLs must use HTTPS; plain HTTP is accepted only for loopback development
hosts (`localhost`, `127.0.0.1`, or `::1`).

## Authentication and health

```bash
python3 scripts/cua.py auth status
python3 scripts/cua.py auth login [--no-prompt | --manual]
python3 scripts/cua.py auth logout
python3 scripts/cua.py ping
python3 scripts/cua.py diagnose
python3 scripts/cua.py self-test
```

When no protected local credential is configured, commands probe `arkcli` through a private `0700` temporary HOME snapshot, select the first personal Agent Plan Max profile (`type=agent-plan`, `plan_tier=max`), and receive a redacted credential handle from the broker. The snapshot is deleted after discovery and the real arkcli state is never modified. If that path is unavailable, use the hidden prompt from a real local terminal. In a non-interactive agent-run command, `auth login` returns `AUTH_REQUIRED` with `arkcli_status`, `arkcli_hint`, and `setup_command` instead of blocking. Credentials are never included in CLI output. `ping`, `diagnose`, and `self-test` do not create a CUA task.

Use `auth login --manual` only when the user explicitly wants a different API key despite an available arkcli profile. It bypasses arkcli for that login, validates a hidden local-terminal input, and stores it in the existing protected cache. Business commands prefer the cache; a rejected manual key does not fall back to arkcli, and `auth logout` removes the override. Never put the key in chat, an option value, or an environment variable.

On success, `auth status` includes only the credential source (`arkcli`,
`manual`, or legacy `cache`). `data.arkcli_profile` is also present for arkcli.

## Core delegation

```bash
python3 scripts/cua.py delegate --objective "<request>" [--wait-ms 0]
python3 scripts/cua.py watch (--invocation-id <id> | --last) [--wait-ms 20000]
python3 scripts/cua.py answer (--invocation-id <id> | --last) --answer "<reply>"
python3 scripts/cua.py result (--invocation-id <id> | --last) [--timeout 600]
python3 scripts/cua.py cancel (--invocation-id <id> | --last)
```

Call `delegate` once and follow `next.command`. Long wait budgets are split into gateway waits of at most 60 seconds. Use `cancel` only on explicit user request.

## Desktop inspection, start/recovery, shutdown, and CUA App access

```bash
python3 scripts/cua.py desktop list
python3 scripts/cua.py desktop access
python3 scripts/cua.py desktop revoke-access (--ticket <ticket> | --access-url <url>)
python3 scripts/cua.py desktop start --idempotency-key <stable-unique-key> \
  [--desktop <id>]
python3 scripts/cua.py desktop shutdown --confirm --idempotency-key <stable-unique-key> \
  [--desktop <id>]
python3 scripts/cua.py desktop operation --operation-id <id>
python3 scripts/cua.py model get
```

`desktop shutdown` calls the gateway's release operation. Use it only after the user explicitly requests shutdown, release, or stopping billing. It immediately ends the billing entitlement, revokes access, interrupts active tasks, and then asynchronously stops or deletes the desktop according to retention policy. If the user wants active work preserved, finish that work first. When `data.operation.recoverable` is true, retain `data.desktop.desktop_id` and the `data.operation.purge_after` deadline; the retention window is normally seven days but the returned deadline is authoritative. Generate one stable unique idempotency key for the approved request and reuse it for any retry; never create a second shutdown request. Follow the returned `next.command` until `desktop operation` reports a terminal status.

`desktop start` is the unified start and recovery interface; there is no separate restore command. Use it only after an explicit user request because successful start or recovery reactivates billable use. The service returns the actual route under `data.action`: `reused`, `starting`, `resuming`, or `allocating`; use `data.restoring` and `data.newly_allocated` to explain the result. Pass the exact shutdown desktop id when the user wants that retained desktop back. Omit it only when service selection or a new primary allocation is acceptable. An exact expired or purged desktop fails instead of silently changing identity. If the response includes an operation id, follow `next.command`: success means the logical desktop, guest readiness, access, and entitlement state are all ready, not merely that the VM started.

`desktop access` calls `GET /v1/desktop/access` and returns a newly issued temporary URL. Give the user `full_interface_url`, falling back to `access_url`. Never reuse a URL from an earlier result. New gateways return the canonical `/desktops/<id>/cua-app/?ticket=...` route directly; legacy gateway URLs are converted without dropping the ticket. Treat URLs and tickets as secrets. Revoke a URL that may have leaked or is no longer needed.

If a URL returns `runtime_capability_required`, do not edit its host or path. Revoke it, run `desktop access` once, and return the newly issued URL. If that fresh URL also fails, stop and report a Desktop Gateway/runtime configuration problem.

The Skill intentionally excludes reboot/reset and persistent model modification. Shutdown and unified start/recovery are its supported mutating desktop lifecycle actions.

## Tasks and reusable contexts

```bash
python3 scripts/cua.py task run --objective "<request>" \
  [--desktop <id-or-name>] [--title "<title>"] [--wait-ms 0]
python3 scripts/cua.py task continue (--context-id <id> | --last-context) \
  --objective "<next step>" [--wait-ms 0]
python3 scripts/cua.py task status (--task-id <id> | --last)
python3 scripts/cua.py task result (--task-id <id> | --last) [--timeout 600]
python3 scripts/cua.py task answer (--task-id <id> | --last) --answer "<reply>"
python3 scripts/cua.py task cancel (--task-id <id> | --last)

python3 scripts/cua.py context list
python3 scripts/cua.py context create [--title "<title>"] [--desktop <id-or-name>]
python3 scripts/cua.py context add-note (--context-id <id> | --last-context) --text "<background>"
python3 scripts/cua.py context show (--context-id <id> | --last-context)
python3 scripts/cua.py timeline show (--context-id <id> | --last-context)
```

Tasks and invocations share the same identifier space. This Skill does not provide an option to suppress CUA's user questions.

## Artifacts

```bash
python3 scripts/cua.py artifact list (--task-id <id> | --last)
python3 scripts/cua.py artifact save (--artifact-id <id> | --last) \
  [--task-id <id>] [--output <new-path>]
```

`artifact save` never overwrites an existing path and does not create a missing parent directory. Omit `--output` to use a secure temporary file. Downloads are limited to 256 MiB; HTML/interstitial content and missing artifacts are not written.

## Credential setup and sync

```bash
python3 scripts/cua.py credentials status [--desktop-id <id>]
python3 scripts/cua.py credentials setup [--desktop-id <id>] [--skip-browser]
python3 scripts/cua.py credentials sync browser --desktop-id <id> <site>...
python3 scripts/cua.py credentials sync env --desktop-id <id> <name>...
python3 scripts/cua.py credentials sync secret --desktop-id <id> <name>...
python3 scripts/cua.py credentials sync credential-set --desktop-id <id> --type <type> --name <name>
python3 scripts/cua.py credentials sync file --desktop-id <id> --profile <profile>
python3 scripts/cua.py credentials reset --desktop-id <id> [--device-id <exact-id>]
```

These commands use the embedded Credential runtime and existing AgentPlan Skill Gateway Credential tools. They do not download or invoke another Skill and do not create a model task. Browser sync accepts explicit signed-Policy site names only; it has no `--all` mode and performs no per-site Chrome permission mutation. See [credentials.md](credentials.md) for the trust boundary and waiting semantics.

`credential-target` is an internal `cua-target/v1` adapter surface used by the embedded orchestration scripts. Agents should not call it directly.
