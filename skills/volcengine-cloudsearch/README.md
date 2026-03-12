# Volcano Engine ESCloud / CloudSearch Skill (OpenClaw)

This repo provides the `volcengine-cloudsearch` skill for OpenClaw. It manages Volcano Engine (Volcengine) **ESCloud/CloudSearch** clusters (Elasticsearch + OpenSearch) and can also run **index/document** operations against an ES/OpenSearch endpoint.

Core capabilities:

- **Control plane (cluster lifecycle):** list/inspect/provision/scale/delete ESCloud instances, query VPC/subnet/zones/specs, manage IP allowlist, reset admin password.
- **Data plane (indices & documents):** connectivity preflight, create/delete/list indices, CRUD documents, search, bulk ingest via `opensearch-py`.

For the authoritative command list and behaviors, see [SKILL.md](SKILL.md), [CONTROL_PLANE.md](CONTROL_PLANE.md), and [DATA_PLANE.md](DATA_PLANE.md).

## Install Into OpenClaw

Place this repo directory under your OpenClaw skills folder (name can vary, content matters). A common layout:

- `.openclaw/skills/openclaw-skill-volcengine-escloud/` (this repository)

## Configure (OpenClaw)

In your `.openclaw/openclaw.json`, enable the skill entry with required Volcano Engine credentials:

```json
{
  "skills": {
    "entries": {
      "volcengine-cloudsearch": {
        "enabled": true,
        "env": {
          "VOLCENGINE_AK": "...",
          "VOLCENGINE_SK": "...",
          "VOLCENGINE_REGION": "cn-beijing"
        }
      }
    }
  }
}
```

Optional environment variables used by the **data plane** (`scripts/data.py`):

- `ESCLOUD_ENDPOINT` (or pass `--endpoint`): `https://domain:9200`
- Basic auth: `ESCLOUD_USERNAME`, `ESCLOUD_PASSWORD`
- API key: `ESCLOUD_API_KEY` (sent as `Authorization: ApiKey <value>`)
- Bearer token: `ESCLOUD_BEARER_TOKEN` (sent as `Authorization: Bearer <value>`)
- TLS: `ESCLOUD_CA_CERTS`, `ESCLOUD_INSECURE`

## Local CLI Usage (Without OpenClaw)

This repo includes two standalone CLIs:

- `scripts/control.py` for **control plane**
- `scripts/data.py` for **data plane**

Create a venv and install dependencies:

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Then run:

```bash
# Control plane examples
./venv/bin/python ./scripts/control.py list
./venv/bin/python ./scripts/control.py detail --id <instance-id>
./venv/bin/python ./scripts/control.py versions

# Data plane (connectivity preflight)
./venv/bin/python ./scripts/data.py --endpoint <https://domain:9200> info
```

## Example Prompts (Inside OpenClaw)

- "List my Volcengine ESCloud instances."
- "Show details for ESCloud instance `<id>`."
- "What ESCloud node specs and versions are available in my region?"
- "Create an ESCloud cluster named `search-prod` in VPC `<vpc>` subnet `<subnet>` with 3 masters and 2 hot nodes."
- "Add my current IP to the ESCloud IP allowlist so I can access the endpoint."
- "Connect to `<endpoint>` and list indices, then create an index called `docs` and insert a document."
- "Run a search query against index `docs` for 'distributed systems'."

## Notes / Scope

- This skill is designed for **Volcano Engine ESCloud/CloudSearch**. It is not intended to manage arbitrary ES/OpenSearch deployments.
- The data-plane CLI does **not** generate embeddings. If you want vector/kNN search, pass vector fields and the appropriate JSON query yourself (see [DATA_PLANE.md](DATA_PLANE.md)).
- Destructive operations (instance delete, index delete, document delete) require explicit confirmation flags (`--confirm`) and should always require explicit user confirmation at the conversation level.
