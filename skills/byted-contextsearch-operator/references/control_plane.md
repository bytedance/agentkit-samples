# Control Plane - Application Console Operations

Use this guide for ContextSearch control-plane goals that correspond to the application console: AgenticSearch creation, scene management, data source/indexer/search-config setup, tools, skills, variables, models, deployments, PSR resources, API keys, and other console operations.

## Contents

- When to use this document
- Quick start
- Output handling
- Intent routing
- AgenticSearch creation workflow
- Console Action Workflow
- Deletion workflow (required)
- Safety rules (MUST)

## When to use this document

Use `control.py` goal-based commands or console action commands when the user asks to:
- Create, inspect, update, publish, start, stop, or delete scenes.
- Create an AgenticSearch scene using the same sequence as the application console.
- Manage AgenticSearch data sources, bindings, variables, skills, tools, chats, users, or context uploads.
- Manage indexer data sources, indexers, indexer jobs, search configs, or search config versions.
- Manage models, deployments, network, pricing, specs, PSR resources, gray release, or API keys.

Runtime retrieval and chat against published context endpoints are outside this skill's scope.

## Quick start

Goal-based command template:

```bash
{baseDir}/venv/bin/python {baseDir}/scripts/control.py <command>
```

If `{baseDir}/venv` does not exist:

```bash
python3 -m venv {baseDir}/venv
{baseDir}/venv/bin/pip install -r {baseDir}/requirements.txt
```

List all console control-plane actions:

```bash
control.py list-actions
```

Run any console action directly:

```bash
control.py <action_snake_case> [forwarded args...]
control.py call-action <action_snake_case> [forwarded args...]
```

Examples:

```bash
control.py create_agentic_data_source \
  --body-json '{"Project":"default","Name":"docs-os","Type":"OPENSEARCH"}' \
  --dry-run

control.py list_indexer \
  --project default \
  --page-number 1 \
  --page-size 10 \
  --dry-run
```

## Output handling

Goal-based wrappers return:

```json
{
  "status": "success|error",
  "goal": "<command>",
  "data": { "...": "..." },
  "steps_completed": ["step1", "step2"]
}
```

Rules:
- If `status == "error"`, stop and surface the error.
- If `status == "success"`, continue to the next workflow step.
- For unfamiliar action bodies, run with `--dry-run` first.

## Intent routing

- "Create AgenticSearch" -> `create-agentic-search`.
- "Create RAG/Image/Video scene" -> `create-scene`.
- "List/search my scenes" -> `list-scenes` or `list_scene`.
- "Show scene detail" -> `get-scene`, `get_scene`, or `get_agentic_scene` depending on scene type.
- "Data source / indexer / search config" -> console actions such as `create_indexer_data_source`, `create_indexer`, `start_indexer_job`, `create_search_config_v2`.
- "Agentic skills/tools/variables/chat/users" -> corresponding `*_agentic_*` console actions.
- "Model/deployment/API key" -> goal-based wrappers or console actions.

## AgenticSearch creation workflow

Copy and track this checklist:

```text
AgenticSearch Creation Progress:
- [ ] Step 1: Collect project, name, and optional description/resource tags
- [ ] Step 2: Run `control.py create-agentic-search`
- [ ] Step 3: Validate returned scene data
- [ ] Step 4: If creation fails at builtin deployment, surface the deployment error
- [ ] Step 5: Continue with data source, tool, skill, or chat setup through console control actions
```

Command:

```bash
control.py create-agentic-search \
  --project default \
  --name <scene-name> \
  --description "<description>"
```

This command aligns with the console flow:

```text
ListAgenticSceneTemplate -> CheckBuiltinDeployment -> DeployBuiltinDeployment -> CreateAgenticScene
```

Rules:
- Do not call `CreateAgenticScene` directly unless `create-agentic-search` cannot cover the task.
- If the builtin deployment is `UNPROVISIONED`, let the workflow deploy it and poll status.
- If polling exits with an error, stop and surface the error instead of retrying a mutation blindly.

## Console Action Workflow

For any application console action:

```text
Console Action Progress:
- [ ] Step 1: Identify the console action with `control.py list-actions`
- [ ] Step 2: Inspect expected body from console behavior or existing docs
- [ ] Step 3: Run `control.py <action> --dry-run ...`
- [ ] Step 4: Execute without `--dry-run`
- [ ] Step 5: Validate JSON output
```

Examples:

```bash
control.py list_agentic_skills \
  --project default \
  --scene-id <scene-id> \
  --page-number 1 \
  --page-size 10

control.py create_agentic_mcp_tool \
  --body-json '<json>'

control.py create_search_config_v2 \
  --body-json '<json>'
```

## Deletion workflow (required)

Never skip confirmation.

```text
Deletion Progress:
- [ ] Step 1: Resolve exact target ID
- [ ] Step 2: Show current state/detail/list row
- [ ] Step 3: Request explicit confirmation phrase containing the exact ID
- [ ] Step 4: Execute delete with `--confirm <target-id>`
- [ ] Step 5: Validate JSON output
```

Goal-based delete examples:

```bash
control.py get-scene --id <scene-id> --scene-type RAG --project default
control.py delete-scene --id <scene-id> --scene-type RAG --project default --confirm <scene-id>

control.py list-api-keys --project default
control.py delete-api-key --id <key-id> --project default --confirm <key-id>
```

Console action delete example:

```bash
control.py delete_agentic_skill \
  --id <skill-id> \
  --project default \
  --confirm <skill-id>
```

## Safety rules (MUST)

- MUST treat console operations as control-plane operations.
- MUST use `control.py` before raw `contextsearch_cli.py` calls.
- MUST require confirmation before delete operations.
- MUST show or fetch the target state before destructive operations.
- MUST avoid fake request bodies, credentials, IDs, or example defaults for create/update operations.
- MUST use [control_tools.md](control_tools.md) only when `control.py` cannot cover the task.
