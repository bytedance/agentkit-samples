# Low-Level API Reference

This document is exclusively for low-level control-plane fallback commands. Use it only when `control.py` or [control_plane.md](control_plane.md) does not cover a specific console operation.

## Entry point

```bash
{baseDir}/venv/bin/python {baseDir}/scripts/contextsearch_cli.py <namespace> <command>
```

Primary fallback namespaces:
- `console`: ContextSearch console OpenAPI actions.
- `openapi`: arbitrary UniversalApi action call for temporary experiments.
- `scene`, `model`, `deployment`, `apikey`: older module-level commands that back the goal-based wrappers.

## Output format

Success:

```json
{"status": "success", "data": { "...": "..." }}
```

Error:

```json
{"error": "...", "details": "..."}
```

## Console action fallback

Prefer this first:

```bash
control.py list-actions
control.py <action_snake_case> [forwarded args...]
```

Fallback list of all console-covered actions:

```bash
contextsearch_cli.py console list
```

Run an action:

```bash
contextsearch_cli.py console <action_snake_case> --body-json '<json>'
```

GET actions can use shortcut query flags:

```bash
contextsearch_cli.py console list_agentic_skills \
  --project default \
  --scene-id <scene-id> \
  --page-number 1 \
  --page-size 10
```

Rules:
- Body payloads must contain business fields only.
- Do not include `Action`, `Version`, `Service`, or signing metadata in the body.
- `network.getV2` maps to `GET` and flattened query parameters.
- `network.postV2` maps to `POST` with JSON body.
- Delete-like console actions require `--confirm`.
- Use `--dry-run` before unfamiliar actions to inspect method/action/body.

## Arbitrary OpenAPI fallback

Use only when neither goal-based commands nor `console list` include the needed action.

```bash
contextsearch_cli.py openapi call \
  --action <ActionName> \
  --method POST \
  --body-json '<json>'
```

Rules:
- Prefer `console` whenever the action exists there.
- Keep service/version defaults unless the console or source code shows otherwise.
- Stop and document the discovered action once the experiment succeeds, so it can become a goal-based command later.

## Coverage reference

See `references/control_coverage.md` for the console-to-skill coverage matrix and action groups.
