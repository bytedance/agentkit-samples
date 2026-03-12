---
name: volcengine-milvus
description: "Manages Milvus on Volcano Engine (Volcengine): provision/inspect/scale/delete clusters and run collection + CRUD/search operations via bundled CLIs. Use when the user mentions Milvus + Volcengine/Volcano Engine or asks to operate Milvus there."
metadata: {"openclaw": {"requires": { "env": ["VOLCENGINE_AK", "VOLCENGINE_SK"] }, "optional": { "env": ["VOLCENGINE_REGION", "MS_EMBEDDING_API_KEY", "MS_EMBEDDING_PROVIDER", "MS_EMBEDDING_BASE_URL", "MS_EMBEDDING_MODEL", "MS_EMBEDDING_DIMENSIONS"] }}}
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

Common control-plane commands:

```bash
# List instances
{baseDir}/venv/bin/python {baseDir}/scripts/control.py list

# Inspect an instance
{baseDir}/venv/bin/python {baseDir}/scripts/control.py detail --id <instance-id>
```

If `{baseDir}/venv` does not exist, create it first:

```bash
python3 -m venv {baseDir}/venv
{baseDir}/venv/bin/pip install -r {baseDir}/requirements.txt
```

## Available operations

**Control Plane** (cluster management): Create, list, inspect, scale, and delete Milvus instances. Query available VPCs, subnets, specs, and versions.
→ See [CONTROL_PLANE.md](CONTROL_PLANE.md) for commands and use cases.

**Data Plane** (collections & data): Create/drop collections, insert/upsert/delete data, vector search, scalar query, and get-by-ID.
→ See [DATA_PLANE.md](DATA_PLANE.md) for commands and use cases.

## Out of scope

- Deploying or operating Milvus outside Volcano Engine (self-hosted, other clouds).
- Deep Milvus performance tuning or schema design beyond basic collection creation and queries.
- Application-level embedding strategy decisions (chunking, RAG design) unless needed to run the provided data plane commands.

## Rules

- **Execution environment**: Always use `{baseDir}/venv/bin/python` to run scripts.
- **Authentication**: `VOLCENGINE_AK` and `VOLCENGINE_SK` are required for all control-plane operations. Data-plane commands also require a reachable Milvus `--endpoint` plus any needed Milvus auth flags; see [DATA_PLANE.md](DATA_PLANE.md).
- **Script usage**: Always prioritize using the provided `scripts/control.py` and `scripts/data.py` to perform tasks. Do not write ad-hoc Python scripts or use the SDK directly unless a specific, complex requirement cannot be met by the existing CLI tools.
- **Destructive actions (strict)**: Never run delete/drop operations until:
  1) You first fetch and show what will be deleted (preview/detail/describe; see [CONTROL_PLANE.md](CONTROL_PLANE.md) and [DATA_PLANE.md](DATA_PLANE.md)).
  2) The user replies with an explicit confirmation phrase that includes the exact target identifier (ID/collection/filter).
  3) You pass that exact target identifier into the CLI `--confirm` argument (where supported).
- **Missing parameters**: Never fail silently. Fetch available options (list VPCs, Subnets, Specs, Collections) and present them to the user interactively.
- **Network access**: Before any data-plane operation, validate the endpoint is reachable. If the instance has no public address (common for newly created instances) or the endpoint is unreachable, fail fast and tell the user to configure a public address and IP whitelist in the Volcano Engine Milvus Web Console, then re-fetch the endpoint via `control.py detail`.
- **Embedding/auto-embedding**: Only use the built-in embedding flags supported by `scripts/data.py` (no custom embedding scripts). Follow the embedding config and input-type rules in [DATA_PLANE.md](DATA_PLANE.md).
- **Vector inputs (strict)**: Do not accept or generate raw vectors for insert/upsert/search. This skill is auto-embedding-only for data writes and semantic search.
- **Language (strict)**: Always reply in the user's language. Use a deterministic heuristic:
  - If the user's message contains any Chinese characters, reply in Chinese.
  - Otherwise, reply in the user's language as inferred from their message.
  - Keep commands/flags/code in English; only the explanation and prompts should be localized.
  - If the user mixes languages and preference is unclear, ask which language they prefer.
