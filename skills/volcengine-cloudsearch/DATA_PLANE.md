# Data Plane — Index & Document Operations (opensearch-py)

## Contents

- Connection details and output format
- Connectivity preflight (required)
- Compatibility / support notes
- Index commands
- Document commands
- Search and bulk commands

---

## Connection Details

All commands: `{baseDir}/venv/bin/python {baseDir}/scripts/data.py --endpoint <endpoint> <command>`

Authentication:
- Basic auth: `--username <user> --password <pass>`
- API key: `--api-key <value>` (sent as `Authorization: ApiKey <value>`)
- Bearer token: `--bearer-token <value>` (sent as `Authorization: Bearer <value>`)

TLS options:
- `--ca-certs <path>` to trust a custom CA bundle
- `--insecure` to disable certificate verification

You can also set defaults using environment variables: `ESCLOUD_ENDPOINT`, `ESCLOUD_USERNAME`, `ESCLOUD_PASSWORD`, `ESCLOUD_CA_CERTS`, `ESCLOUD_INSECURE`, `ESCLOUD_API_KEY`, `ESCLOUD_BEARER_TOKEN`.

---

## Connectivity preflight (required)

Before running any data-plane command, do a quick reachability check:

```bash
data.py --endpoint <https://domain:9200> info
```

If `info` fails, stop and inform the user to:
- Verify endpoint is correct and reachable from their network
- Check ESCloud IP allowlist settings (use control plane `ip_allowlist_get/ip_allowlist_set`)
- Verify credentials (basic auth / API key / bearer token)

---

## Support Notes

- Tested targets:
  - Elasticsearch **7.10**: supported for all v1 commands.
  - OpenSearch **2.9 / 3.3**: supported for all v1 commands.
  - Elasticsearch **8.x**: **limited support** (core CRUD/search/bulk only). If a request fails due to compatibility requirements, report that ES 8.x support is limited and the endpoint may require compatibility headers or different auth/security settings.

## Vector / kNN search and embeddings

- The CLI does **not** generate embeddings and does **not** require them.
- If your index has vector fields and the engine supports it, you can run vector/kNN queries by passing the appropriate JSON to `search --query '{...}'`.

---

## Output Format

Success:

```json
{"status":"success","data":{...}}
```

Error:

```json
{"error":"...","details":"..."}
```

---

## Commands

### info

```bash
data.py --endpoint <endpoint> info
```

### index_create

```bash
data.py --endpoint <endpoint> index_create --index <name> [--settings '{}' ] [--mappings '{}' ]
```

### index_delete

**Require explicit user confirmation before executing.**

```bash
data.py --endpoint <endpoint> index_delete --index <name> --confirm
```

### index_exists

```bash
data.py --endpoint <endpoint> index_exists --index <name>
```

### index_list

```bash
data.py --endpoint <endpoint> index_list
```

### index_get

```bash
data.py --endpoint <endpoint> index_get --index <name>
```

### doc_index

```bash
data.py --endpoint <endpoint> doc_index --index <name> --doc '{"field":"value"}' [--id <id>] [--refresh true|false]
```

### doc_get

```bash
data.py --endpoint <endpoint> doc_get --index <name> --id <id>
```

### doc_delete

**Require explicit user confirmation before executing.**

```bash
data.py --endpoint <endpoint> doc_delete --index <name> --id <id> --confirm [--refresh true|false]
```

### search

```bash
data.py --endpoint <endpoint> search --index <name> --query '{"query":{"match_all":{}}}' [--from 0] [--size 10]
```

### bulk

```bash
data.py --endpoint <endpoint> bulk --file <path.ndjson>
```

or

```bash
data.py --endpoint <endpoint> bulk --body $'{"index":{"_index":"docs","_id":"1"}}\n{"title":"hello"}\n'
```
