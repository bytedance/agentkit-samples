---
name: volcengine-cloudsearch
description: "Manages Volcano Engine (Volcengine) ESCloud/CloudSearch (Elasticsearch + OpenSearch) clusters: control plane provisioning/scale/delete via volcengine-python-sdk and data plane index/doc CRUD + search via opensearch-py. Use when the user mentions ESCloud/CloudSearch/Elasticsearch/OpenSearch on Volcengine/Volcano Engine or asks to provision/operate those clusters there."
metadata: {"openclaw": {"requires": { "env": ["VOLCENGINE_AK", "VOLCENGINE_SK"] }, "optional": { "env": ["VOLCENGINE_REGION", "ESCLOUD_ENDPOINT", "ESCLOUD_USERNAME", "ESCLOUD_PASSWORD", "ESCLOUD_CA_CERTS", "ESCLOUD_INSECURE", "ESCLOUD_API_KEY", "ESCLOUD_BEARER_TOKEN"] }}}
user-invocable: true
---

# Volcano Engine ESCloud (Elasticsearch + OpenSearch)

Manage ESCloud instances on Volcano Engine — cluster lifecycle (control plane) and index/doc operations (data plane).

## Choose the right plane

- **Provision / scale / delete instances?** → use `scripts/control.py` and read [CONTROL_PLANE.md](CONTROL_PLANE.md)
- **Create indices / write docs / search / bulk ingest?** → use `scripts/data.py` and read [DATA_PLANE.md](DATA_PLANE.md)

## Setup (once per environment)

Create a Python venv on first use (not bundled in the repo):

```bash
cd {baseDir}
python3 -m venv {baseDir}/venv
{baseDir}/venv/bin/pip install -r {baseDir}/requirements.txt
```

Then run scripts with the venv Python:

```bash
cd {baseDir}
{baseDir}/venv/bin/python {baseDir}/scripts/control.py <command>
{baseDir}/venv/bin/python {baseDir}/scripts/data.py <command>
```

If you see a "Missing Dependency" error at runtime, (re)install dependencies:

```bash
cd {baseDir}
{baseDir}/venv/bin/python -m pip install -r {baseDir}/requirements.txt
```

## Quick start (common tasks)

```bash
# List instances
{baseDir}/venv/bin/python {baseDir}/scripts/control.py list

# Inspect an instance
{baseDir}/venv/bin/python {baseDir}/scripts/control.py detail --id <instance-id>

# Show supported versions (best-effort)
{baseDir}/venv/bin/python {baseDir}/scripts/control.py versions

# Check connectivity (data plane)
{baseDir}/venv/bin/python {baseDir}/scripts/data.py --endpoint <https://domain:9200> info
```

## Available operations

**Control Plane** (instance management): Create, list, inspect, scale, and delete ESCloud instances. Query VPCs, subnets, zones, and node specs. Manage IP allowlist and reset admin password.
→ See [CONTROL_PLANE.md](CONTROL_PLANE.md) for commands and workflows.

**Data Plane** (index & documents): Create/delete/list indices, write/read/delete documents, search, and bulk ingest via `opensearch-py`. Works with OpenSearch and (limited) Elasticsearch.
→ See [DATA_PLANE.md](DATA_PLANE.md) for commands and workflows.

## Out of scope

- Running or managing ES/OpenSearch outside Volcano Engine.
- Embedding generation (you must provide vectors if you want vector search).
- Advanced admin features (ILM/snapshots/security) unless added explicitly later.

## Rules

- **Execution environment**: Always use `{baseDir}/venv/bin/python` to run scripts.
- **Authentication**: `VOLCENGINE_AK` and `VOLCENGINE_SK` are required for all control-plane operations. `VOLCENGINE_REGION` is optional (default: `cn-beijing`).
- **Destructive actions**: Always require explicit user confirmation before running delete operations (instance delete, index delete, delete-by-query, etc.). The CLIs also require `--confirm` for delete commands.
- **Missing parameters**: Never fail silently. If IDs/specs are missing, fetch available options (VPCs, subnets, node specs) and present them to the user.
- **Connectivity**: Before data-plane operations, validate the endpoint is reachable (run `data.py info`). If unreachable, fail fast and advise checking IP allowlist / public endpoint / credentials.
- **Language**: Reply in the user's preferred language.
