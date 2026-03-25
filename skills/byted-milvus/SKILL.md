---
name: byted-milvus
description: Manages Milvus on Volcano Engine (Volcengine): provision/inspect/scale/delete clusters and run collection + CRUD/search operations via bundled CLIs. Use when the user mentions Milvus + Volcengine/Volcano Engine or asks to operate Milvus there.
metadata: {"openclaw": {"requires": { "env": [] }}}
user-invocable: true
---

# Volcano Engine Milvus

Manage Milvus instances on Volcano Engine — cluster lifecycle and vector data operations.

## Quick Start

Use the bundled CLIs (always run via the skill venv):

```bash
{baseDir}/venv/bin/python {baseDir}/scripts/control.py <command>
{baseDir}/venv/bin/python {baseDir}/scripts/data.py <command>
```

If `{baseDir}/venv` does not exist:

```bash
python3 -m venv {baseDir}/venv
{baseDir}/venv/bin/pip install -r {baseDir}/requirements.txt
```

See [CONTROL_PLANE.md](CONTROL_PLANE.md) and [DATA_PLANE.md](DATA_PLANE.md) for workflows and examples.

Low-level control-plane fallback (use only when goal-based commands do not cover the task):
`{baseDir}/venv/bin/python {baseDir}/scripts/control_tools.py <command>`

## Available operations

**Control Plane** (cluster management): Use goal-based workflows to provision, inspect, scale, delete, and expose Milvus instances.
→ See [CONTROL_PLANE.md](CONTROL_PLANE.md) for goal-based commands and workflows.
→ See [CONTROL_TOOLS.md](CONTROL_TOOLS.md) for low-level `control_tools.py` fallback commands (use only when `CONTROL_PLANE.md` does not cover the task).

**Data Plane** (collections & data): Create/drop collections, insert/upsert/delete data, vector search, scalar query, and get-by-ID.
→ See [DATA_PLANE.md](DATA_PLANE.md) for commands and use cases.

## Out of scope

- Deploying or operating Milvus outside Volcano Engine (self-hosted, other clouds).
- Deep Milvus performance tuning or schema design beyond basic collection creation and queries.
- Application-level embedding strategy decisions (chunking, RAG design) unless needed to run the provided data plane commands.

## Rules

**Common**
- **Execution environment**: Always use `{baseDir}/venv/bin/python` to run scripts.
- **Authentication**: `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` are required for all control-plane operations. Data-plane commands also require a reachable Milvus `--endpoint` plus any needed Milvus auth flags. See [DATA_PLANE.md](DATA_PLANE.md).
- **Script usage**: Prioritize `scripts/control.py` and `scripts/data.py`. Use `scripts/control_tools.py` only as a last resort when goal-based commands do not cover the task. Do not write ad-hoc Python scripts or use the SDK directly unless existing CLIs cannot satisfy a specific requirement.
- **Language (strict)**: Always reply in the user's language. Use a deterministic heuristic:
  - If the user's message contains any Chinese characters, reply in Chinese.
  - Otherwise, reply in the user's language as inferred from their message.
  - Keep commands/flags/code in English; only the explanation and prompts should be localized.
  - If the user mixes languages and preference is unclear, ask which language they prefer.

**Control plane**
- **Destructive actions (strict)**: Never run delete operations until:
  1) You first fetch and show what will be deleted (preview/detail/describe; see [CONTROL_PLANE.md](CONTROL_PLANE.md)).
  2) The user replies with an explicit confirmation phrase that includes the exact target identifier.
  3) You pass that exact target identifier into the CLI `--confirm` argument.
- **Missing parameters**: Never fail silently. Fetch available options (VPCs, Subnets, Specs) and present them to the user interactively.
- **EIP Auto-Reuse**: When enabling public endpoints with `enable-public` or `ms-enable-public`, prefer using `--eip-auto-reuse true` to leverage existing unbinded EIPs and avoid quota failures.

**Data plane**
- **Network access**: Before any data-plane operation, validate the endpoint is reachable. If the instance has no public address or is unreachable, use the `enable-public` or `ms-enable-public` control workflows to expose the instance and set IP allow-groups (whitelists), then re-fetch the endpoint via `status`.
- **Embedding/auto-embedding**: Only use the built-in embedding flags supported by `scripts/data.py` (no custom embedding scripts). Follow the embedding config and input-type rules in [DATA_PLANE.md](DATA_PLANE.md).
- **Vector inputs (strict)**: Do not accept or generate raw vectors for insert/upsert/search. This skill is auto-embedding-only for data writes and semantic search.
