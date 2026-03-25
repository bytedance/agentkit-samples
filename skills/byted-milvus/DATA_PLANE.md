# Data Plane — Collections & Operations

## Contents

- Connection details and output format
- Embedding rule
- Conditional workflow (decision tree)
- "Search" disambiguation (semantic default)
- Collection commands: create, drop, has, list, describe
- Data commands: insert, upsert, read, delete, search, get

---

## Connection Details

All commands: `{baseDir}/venv/bin/python {baseDir}/scripts/data.py <command>`

Every command requires: `--endpoint <endpoint>`. Authentication flags depend on the deployment:
- Typical username/password auth: `--username <username> --password <password>`
- Token auth: `--username <token>` (omit `--password`)
- No auth: omit both `--username` and `--password` (only if the endpoint allows it)

These are omitted from examples below for brevity, but MUST always be included where applicable.

## Connectivity preflight (required)

Before running any data-plane command, do a quick reachability check.

1) Get the endpoint from `control.py detail --id <instance-id>`.
2) Inspect `endpoint_list` in the detail output:
   - Prefer an endpoint with `type: "MILVUS_PUBLIC"` and a non-null `eip`.
   - If only `type: "MILVUS_PRIVATE"` is present (or `MILVUS_PUBLIC` has `eip: null`), treat it as **no public address configured** and stop.
   - Avoid using the `ip` field as the endpoint; use the `domain` value (includes port).
3) Validate connectivity by running a lightweight `data.py` command (e.g., `list_collections`) against the selected endpoint and treat any connection failure as a **hard stop**.

If the endpoint is unreachable, fail fast and inform the user (do not attempt further diagnosis or workarounds):
- Newly created instances often have **no public address** by default.
- The SDK/CLI does not currently support binding/enabling public access.
- The user must configure **Public Address** and **IP whitelist** in the Volcano Engine Milvus Web Console (select the correct region), then re-run `control.py detail` to obtain the public endpoint.

## Output Format

All commands return JSON: `{"status": "success", "data": { ... }}` or `{"error": "...", "details": "..."}`.

## Embedding Rule

Prefer environment-based configuration. Set `MS_EMBEDDING_API_KEY`, `MS_EMBEDDING_PROVIDER`, `MS_EMBEDDING_MODEL`, and `MS_EMBEDDING_BASE_URL` to avoid being prompted for these during runtime.

Auto-embedding decision rules:
- If the user input is **text** (documents to insert/upsert, or a text query to search), use **auto-embedding** flags.
- Direct vector inputs are **not supported** in this skill. Always use auto-embedding for insert/upsert/search.

Auto-embedding config rules:
- First check env vars: `MS_EMBEDDING_API_KEY`, `MS_EMBEDDING_PROVIDER`, `MS_EMBEDDING_MODEL`, `MS_EMBEDDING_BASE_URL`.
- If any embedding env vars are missing or empty, ask the user to provide the embedding configuration (do not guess).
- Never fabricate vectors: this skill is auto-embedding-only. If embeddings are not configured, stop and ask for embedding configuration instead of inventing placeholder vectors.
- Schema safety: when auto-embedding, verify the embedding output dimension matches the collection vector field dimension via `describe_collection` before inserting/searching. The CLI enforces this by default; use `--no-verify-schema` only if the user explicitly requests it.

Optional reduced embedding dimensions:
- Supported via `MS_EMBEDDING_DIMENSIONS` env var or `--embed-dimensions <n>` flag on `insert`, `upsert`, and `search` (text query auto-embedding).
- Only use this if the chosen provider/model supports reduced dimensions.
- Collection schema must match: if you reduce embedding dimensions to `<n>`, the collection vector field dimension must also be `<n>`.

Volcengine (Doubao) embedding model suggestions (if user chooses `MS_EMBEDDING_PROVIDER=volcengine` and has not configured a model yet):
- `doubao-embedding-large-text-250515` (2048 dims, latest)
- `doubao-embedding-large-text-240915` (4096 dims)
- `doubao-embedding-text-240715` (2560 dims)
- `doubao-embedding-text-240515` (2048 dims)

Always confirm that the collection vector dimension matches the selected model:
- Creating a collection: choose `--dimension` to match the model dims.
- Using an existing collection: run `describe_collection` and verify the vector field dimension before inserting/searching.

Hard rule: Never write custom scripts to operate data or perform embeddings. Only use the provided `scripts/data.py` commands and flags.

---

## Conditional Workflow

Determine the operation type and follow the appropriate path:

**Need the endpoint?** → Use control plane first
  - Run `control.py detail --id <instance-id>` and pick a public endpoint with non-null `eip` (see Connectivity preflight).

**Managing collections?** → Use Collection Commands below
  - Creating? → `create_collection`
  - Inspecting? → `describe_collection`, `has_collection`, `list_collections`
  - Dropping? → **Require user confirmation** → `drop_collection`

**Writing data?** → Use `insert` or `upsert`
  - This skill is **auto-embedding only**:
    - Check env vars `MS_EMBEDDING_API_KEY`, `MS_EMBEDDING_PROVIDER`, `MS_EMBEDDING_MODEL`, `MS_EMBEDDING_BASE_URL`
    - If not configured, ask the user for embedding configs, then run `data.py insert/upsert` with auto-embedding flags
  - Hard rule: Do not accept or generate vectors manually; do not pass vectors in `--data`.

**Reading data?**
  - User asks "search" / "查询" / "搜索" / "检索"? → Default to **semantic search** (`search`), but apply the disambiguation rules below.
  - Semantic search (text similarity via auto-embedding)? → `search`
    - Text query → use auto-embedding (check embedding env vars first; if missing, ask user for configs)
    - Direct vector queries are **not supported** in this skill.
  - Scalar filter query (field conditions)? → `read` with `--filter`
  - Fetch by primary key? → `get` with `--ids`

### Disambiguating "search" (semantic default, scalar supported)

In user messages, "search" may mean semantic similarity search or scalar filtering. Use these rules:

1) Default: If the user only says "search" without clear field conditions, interpret as **semantic search**.

2) Auto-route to scalar: If the user includes obvious predicate structure, interpret as **scalar filter query** (`read --filter`).
Common language-agnostic signals:
- Operators: `=`, `!=`, `>`, `<`, `>=`, `<=`
- Key/value patterns: `field:value`, `field=value`
- Ranges/dates/numbers paired with comparators (e.g., `created_at >= 2025-01-01`, `price < 10`)

3) Explicit override (works in any language): If the user prefixes their intent, follow it:
- `filter:` / `where:` / `条件:` → treat as scalar filter query (`read --filter`)
- `semantic:` / `text:` → treat as semantic search (`search`)

4) Mixed intent: If the user provides both a semantic query and filter-like predicates, treat it as **semantic search with an optional filter**:
- Use `data.py search ... --filter '<expression>'` when they want similarity ranking plus constraints.

5) Only if still ambiguous after applying (1)-(4): ask one clarifying question and stop.
Prompt template:
- "Do you want semantic similarity search (text via auto-embedding) or a scalar filter query (field conditions)? If scalar, please provide a filter expression."

**Deleting data?** → Ask for filter expression → `delete`

---

## Collection Commands

### create_collection

Before creating a collection, confirm the schema-related options with the user. The CLI supports these parameters.

Two modes:
- **Custom schema (recommended)**: use `--schema-file` / `--schema-json` to define explicit fields (e.g., `VARCHAR` raw text + vector field). This avoids relying on dynamic fields.
- **Fast schema (legacy/simple)**: use `--dimension` + a few flags to create a minimal schema (primary key + one vector field).

**Required input**: Always ask the user for the vector dimension (integer). Do not assume/default it.
- Fast schema: provide `--dimension <n>`.
- Custom schema: set `dim: <n>` for each `FLOAT_VECTOR` field in the schema JSON.

Schema confirmation checklist (ask/confirm explicitly):
- `primary_field_name` (default: `id`)
- `id_type` (default: `int`; alternative: `string`)
- `auto_id` (default: `true`)
- `vector_field_name` (default: `vector`)
- `metric_type` (default: `COSINE`)
- `enable_dynamic_field` (default: disabled; prefer explicit schema)
- `pk_max_length` (only if `id_type` is `string`)

Prefer custom schema (recommended for production):
- Use `--schema-file <path>` or `--schema-json '<json>'` to define explicit fields (e.g., a `VARCHAR` raw text field plus a vector field), instead of relying on dynamic fields.

Schema JSON shape (v1):
- `enable_dynamic_field`: boolean (default: false)
- `primary_key`: optional object (recommended; easier than tagging a field):
  - `name`: string
  - `type`: `INT64` | `VARCHAR` (aliases: `INT`, `STRING`)
  - `auto_id`: boolean (only valid for INT64 primary key)
  - `max_length`: int (required for VARCHAR primary key)
- `dimension`: optional int default for `FLOAT_VECTOR` fields (still allowed to override per field via `dim`)
- `varchar_max_length`: optional int default for `VARCHAR` fields (still allowed to override per field via `max_length`)
- `fields`: array of:
  - `name`: string
  - `type`: `INT64` | `VARCHAR` | `FLOAT_VECTOR` (aliases: `INT`, `STRING`, `VECTOR`)
  - `dim`: int (required for FLOAT_VECTOR unless `dimension` is set)
  - `max_length`: int (required for VARCHAR unless `varchar_max_length` is set)
  - `nullable`: boolean (optional)
  - `description`: string (optional)
- `index`: optional:
  - `field_name`: string (vector field; defaults to the first vector field)
  - `index_type`: string (default: `AUTOINDEX`)
  - `metric_type`: string (default: `COSINE`)
  - `params`: object (optional)

Prompt template:
- "What vector dimension should this collection use (e.g., `768`, `1024`, `1536`, `2048`, `2560`)? It must match the embedding model (or `--embed-dimensions` if you reduce dims)."
- "Please confirm the collection schema options (or accept defaults): primary field (`id`), id type (`int` or `string`), auto-id, vector field name, metric type, and whether to enable dynamic fields."

```bash
data.py create_collection --collection <name> --dimension <dim> \
  --primary-field-name <pk-field> --id-type <int|string> [--no-auto-id] \
  --vector-field-name <vector-field> --metric-type <COSINE|L2|IP> \
  [--enable-dynamic-field|--disable-dynamic-field] [--pk-max-length <n>]
```

Custom schema example (stores raw text + embedded vectors computed by auto-embedding):

```bash
data.py create_collection --collection docs --schema-json '{
  "enable_dynamic_field": false,
  "primary_key": {"name": "id", "type": "INT64", "auto_id": true},
  "dimension": 2048,
  "varchar_max_length": 65535,
  "fields": [
    {"name": "text", "type": "VARCHAR"},
    {"name": "vector", "type": "FLOAT_VECTOR"}
  ],
  "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"}
}'
```

### drop_collection

**Low freedom — require explicit user confirmation before executing. Do not drop without it.**

The CLI enforces confirmation via `--confirm <collection>`. Preview must be explicit: run `describe_collection` first (do not rely on the drop command for preview).

Workflow (required):
1) Run `describe_collection` and show the user the target collection name + schema summary.
2) Ask the user to reply with an explicit phrase that includes the exact collection name (e.g., "Yes, drop <name>").
3) Only then run `drop_collection` with `--confirm <name>`.

```bash
data.py describe_collection --collection <name>
data.py drop_collection --collection <name> --confirm <name>
```

### has_collection

```bash
data.py has_collection --collection <name>
```

### list_collections

```bash
data.py list_collections
```

### describe_collection

```bash
data.py describe_collection --collection <name>
```

---

## Data Commands

### insert

```bash
data.py insert --collection <name> --data '<json-array>'
```

Input-type rule:
- If `--data` contains **raw text** fields (strings) and the collection expects a vector field, use **Auto-Embedding**.
- Direct vector inputs (numeric arrays) are **not supported** in this skill. Always use **Auto-Embedding**.

**Auto-Embedding**: Add `--embed-provider <provider> --embed-model <model> --embed-field <vector-field> --text-field <text-field>`.
Before choosing provider/model, check env vars `MS_EMBEDDING_API_KEY`, `MS_EMBEDDING_PROVIDER`, `MS_EMBEDDING_MODEL`, and `MS_EMBEDDING_BASE_URL`; if any are missing/empty, ask the user.
If using reduced dimensions, pass `--embed-dimensions <n>` (or set `MS_EMBEDDING_DIMENSIONS=<n>`) and ensure the collection vector field dimension is `<n>`.
By default, the CLI verifies schema vs embedding config before auto-embedding; add `--no-verify-schema` only if the user explicitly requests skipping validation.

Example with embedding:

```bash
data.py insert --collection docs --data '[{"text": "hello world"}]' --embed-provider openai --embed-model text-embedding-3-small --text-field text --embed-field vector
```

### upsert

```bash
data.py upsert --collection <name> --data '<json-array>'
```

Auto-Embedding: same flags as `insert`.

### read

```bash
data.py read --collection <name> --filter '<expression>' --limit <n>
```

### delete

```bash
data.py delete --collection <name> --filter '<expression>' --confirm '<expression>'
```

Workflow (required):
1) Preview what matches the filter using `read` (do not rely on the delete command for preview).
2) Show the user the collection + filter + preview.
3) Ask the user to reply with an explicit phrase that includes the exact filter string (e.g., `Yes, delete where <expression>`).
4) Only then run `delete` with `--confirm '<expression>'`.

### search

```bash
data.py search --collection <name> --anns-field <vector-field> --data '<json-array>' --limit <n>
```

Input-type rule:
- Text query: `--data '["query text"]'` → requires `--embed-provider <provider> --embed-model <model>` (check env vars first; if missing, ask user).
- Direct vector queries (numeric arrays) are **not supported** in this skill.

**Text search** (auto-embed query): `--data '["query text"]'` with `--embed-provider <provider> --embed-model <model>`.
Before running text search, check env vars `MS_EMBEDDING_API_KEY`, `MS_EMBEDDING_PROVIDER`, `MS_EMBEDDING_MODEL`, and `MS_EMBEDDING_BASE_URL`; if any are missing/empty, ask the user.
If using reduced dimensions, pass `--embed-dimensions <n>` (or set `MS_EMBEDDING_DIMENSIONS=<n>`) and ensure the collection vector field dimension is `<n>`.
By default, the CLI verifies schema vs embedding config before auto-embedding; add `--no-verify-schema` only if the user explicitly requests skipping validation.

Example:

```bash
data.py search --collection docs --anns-field vector --data '["find documents about AI"]' --limit 5 --embed-provider openai --embed-model text-embedding-3-small
```

### get

```bash
data.py get --collection <name> --ids '<json-array-of-ids>'
```
