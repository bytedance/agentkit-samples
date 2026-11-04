# BytePlus RuntimeTemplate HTTP API Example

Select a Workspace with `--workspace-id <id>`, `HARNESS_INFRA_WORKSPACE_ID`
(also `AGENTKIT_WORKSPACE_ID`), then top-level YAML `workspace_id`, in that order.
Create/Get/List send `WorkspaceId`; returned ownership is saved to the config.
Omission/empty selection uses the unique ACTIVE DEFAULT Workspace.
Keep polling and pagination in the same scope. Cross-Workspace Get returns not
found and NextToken cannot be reused in another Workspace. Update/Delete locate
templates by ID. The server resolves cloud ProjectName from Workspace.

New templates require a Ready account-level SessionStore reference via
`--session-store-id`, `AGENTKIT_SESSION_STORE_ID`, or
`runtime_template.session_store_id`. It cannot be combined with
`DATABASE_POSTGRESQL_*` / `DATABASE_MYSQL_*` environment variables.

[火山引擎中文](README.md)

This example calls the complete RuntimeTemplate lifecycle through the BytePlus
TOP HTTP endpoint without the AgentKit SDK:

1. `CreateRuntimeTemplate`
2. `GetRuntimeTemplate`
3. `ListRuntimeTemplates`
4. `UpdateRuntimeTemplate`
5. `DeleteRuntimeTemplate`

Requests use API Version `2025-10-30` and are sent to
`https://agentkit.ap-southeast-1.byteplusapi.com`. The field-level contract follows
`akx origin/master:docs/harness-infra/api/runtime-template-api.md`.

## 1. Install Dependencies

```bash
cd python/01-tutorials/01-agentkit-runtime/runtime_template_http
uv venv --allow-existing
uv pip install -r requirements.txt \
  --index-url https://mirrors.aliyun.com/pypi/simple/
source .venv/bin/activate
```

## 2. Create the Configuration File

```bash
cp -n config.yaml.example config.yaml
chmod 600 config.yaml
```

Set the `runtime_template` creation specification in `config.yaml`. The scripts
resolve this file relative to their own directory, independently of the current
working directory. Use `--config <path>` or
`AGENTKIT_RUNTIME_TEMPLATE_CONFIG` to select another file. CLI arguments
override the corresponding YAML values.

The included control-plane fields target Volcengine. For BytePlus, keep the
RuntimeTemplate specification in YAML and provide the BytePlus endpoint and
credentials through the existing provider variables:

```bash
export AGENTKIT_CLOUD_PROVIDER=byteplus
export BYTEPLUS_ACCESS_KEY='<access-key>'
export BYTEPLUS_SECRET_KEY='<secret-key>'
export BYTEPLUS_AGENTKIT_REGION=ap-southeast-1
```

`runtime_template.name_prefix` receives a UTC timestamp and random suffix
automatically because deleted template names cannot be reused.

Set `runtime_template.role_name` to a pre-created Runtime execution role in the
current account. This example does not create or modify BytePlus IAM roles.
Continue to provide temporary credentials through
`BYTEPLUS_AGENTKIT_SESSION_TOKEN`.

## 3. Preview Create

`--dry-run` does not load credentials, access the network, or update runtime
state in the configuration:

```bash
python 01_create_runtime_template.py --dry-run --json
```

## 4. Create and Wait for Ready

```bash
python 01_create_runtime_template.py --wait
```

When YAML contains `image_url: null` and `runtime: {}`, the service defaults
are used. Supply an image only when the current account can pull it.

The service stores `Envs` in plaintext and returns them from Get. Never put API
keys, tokens, passwords, or other secrets in this field.

After Create succeeds, the script writes the template ID, status, and Endpoint
to `runtime_template.id/status/endpoint` in `config.yaml`. Subsequent commands
read these fields automatically without a separate local state path.

## 5. Get and Paginate

```bash
python 02_get_runtime_template.py
python 03_list_runtime_templates.py --max-results 1 --all
```

For a single page, pass the returned cursor to
`--next-token '<previous-next-token>'`.

## 6. Update Description and Meta

```bash
python 04_update_runtime_template.py \
  --description 'Updated description' \
  --meta '{"purpose":"review"}' \
  --wait
```

This API creates and manages the associated Runtime, so only `Description` and
`Meta` can be updated. `Resources`, `ImageUrl`, `Runtime`, `Name`, `RoleName`,
and `Envs` cannot be updated in place. Create a replacement template when these
settings must change.

To clear description and metadata:

```bash
python 04_update_runtime_template.py \
  --clear-description \
  --clear-meta
```

## 7. Delete and Verify

Remove active Session and Environment references before deletion:

```bash
python 05_delete_runtime_template.py \
  --reason 'Tutorial resource cleanup' \
  --wait
```

`--wait` calls Get until the service returns `404 ResourceNotFound`. After
confirmation, the script clears `id/status/endpoint` in `config.yaml`.

## Idempotent Retries

Create, Update, and Delete use `ClientToken`. If a result is uncertain, reuse
the original token and every original request field. Use a new token for a new
operation.

## State, Security, and Tests

At runtime, only Endpoint, RuntimeTemplateId, and Status are written back to
`config.yaml`. Response `Envs` and complete request bodies are not persisted.
The configuration mode is fixed at `0600`. Select a template explicitly with
`AGENTKIT_RUNTIME_TEMPLATE_ID` or `--runtime-template-id`.

```bash
uv run --with-requirements requirements.txt \
  python -m unittest discover -s tests -v
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTKIT_RUNTIME_TEMPLATE_CONFIG` | `./config.yaml` | YAML config path |
| `AGENTKIT_HTTP_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `AGENTKIT_HTTP_ATTEMPTS` | `3` | Attempts for network errors, 429, and 503 |
| `AGENTKIT_POLL_INTERVAL_SECONDS` | `5` | Poll interval |
| `AGENTKIT_POLL_TIMEOUT_SECONDS` | `900` | Overall poll timeout |

See [doc/runtime_template_contract.md](doc/runtime_template_contract.md) for
the contract boundaries.
