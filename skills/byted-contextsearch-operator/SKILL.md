---
name: byted-contextsearch-operator
description: "Manages Volcano Engine ContextSearch control-plane and application-console operations. Use for ContextSearch scene, AgenticSearch, data source, indexer, search-config, model, deployment, network, specification, and API-key administration. Do not use for generic web search or runtime RAG, image, or video retrieval and chat."
version: "1.0.1"
metadata:
  openclaw:
    requires:
      env:
        - VOLCENGINE_AK
        - VOLCENGINE_SK
    optional:
      env:
        - VOLCENGINE_REGION
        - VOLCENGINE_SCHEMA
license: Apache-2.0
---

# Volcano Engine ContextSearch

Manage ContextSearch application-console and control-plane operations on Volcano Engine.

## Quick Start

Use the bundled CLIs (always run via the skill venv):

```bash
{baseDir}/venv/bin/python {baseDir}/scripts/control.py <command>
```

If `{baseDir}/venv` does not exist:

```bash
python3 -m venv {baseDir}/venv
{baseDir}/venv/bin/pip install -r {baseDir}/requirements.txt
```

See [references/control_plane.md](references/control_plane.md) for workflows and examples.

Low-level fallback (use only when goal-based commands do not cover the task):

```bash
{baseDir}/venv/bin/python {baseDir}/scripts/contextsearch_cli.py <namespace> <command>
```

See [references/control_tools.md](references/control_tools.md) and [references/control_coverage.md](references/control_coverage.md).

## Available operations

Use goal-based workflows and console action commands to create AgenticSearch and manage scenes, data sources, indexers, search configs, Agentic tools/skills/variables/chats/users, models, deployments, PSR resources, network, specs, and API keys.
→ See [references/control_plane.md](references/control_plane.md).

**Low-level tools**: Use `scripts/contextsearch_cli.py console` or `openapi` only when `control.py` does not cover a specific console action.
→ See [references/control_tools.md](references/control_tools.md).

## Out of scope

- Operating non-Volcano-Engine ContextSearch deployments.
- Runtime RAG, image, or video retrieval and chat against published context endpoints.
- Generic web search, research, or best-practice lookup; use an available web-search capability instead.
- Designing full application-level RAG/AgenticSearch architecture beyond the fields needed to run the provided commands.
- Guessing unknown request bodies, IDs, or credentials. If a body shape is not clear, inspect the relevant console request shape or ask the user for required fields.

## Rules

**Common**
- **Execution environment**: Always use `{baseDir}/venv/bin/python` to run scripts.
- **Control-plane authentication**: Console operations require `VOLCENGINE_AK` and `VOLCENGINE_SK`. Use `VOLCENGINE_REGION` only when the default `cn-beijing` is not correct.
- **Script usage**: Use `scripts/control.py` for console operations. Use `scripts/contextsearch_cli.py` only as a last resort when `control.py` does not cover the console action.
- **Console parity**: For AgenticSearch creation, use `control.py create-agentic-search`; it follows the console chain `ListAgenticSceneTemplate -> CheckBuiltinDeployment -> DeployBuiltinDeployment -> CreateAgenticScene`.
- **Output handling**: Commands return JSON. Make decisions from `status`, `goal`, `data`, and `steps_completed`.
- **Language (strict)**: Always reply in the user's language. If the user's message contains Chinese characters, reply in Chinese. Keep commands/flags/code in English.

- **Console boundary**: Treat ContextSearch console operations as control-plane operations, including Agentic data source/indexer/search-config setup.
- **Destructive actions (strict)**: Never run delete operations until:
  1. You first fetch and show what will be deleted.
  2. The user replies with an explicit confirmation phrase that includes the exact target identifier.
  3. You pass that exact target identifier into the CLI `--confirm` argument when the goal-based command supports it.
- **Missing parameters**: Never fail silently. Inspect available resources or ask one concise question.
- **Mutation retry safety**: If a mutation may have been submitted but the result is unclear, observe with a get/list command before retrying.
