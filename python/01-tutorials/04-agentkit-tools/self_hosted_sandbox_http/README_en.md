# EnvironmentResource HTTP examples

All scripts accept `--workspace-id <id>`, ahead of `HARNESS_INFRA_WORKSPACE_ID`
(also `AGENTKIT_WORKSPACE_ID`). Create/Get/List send PascalCase `WorkspaceId`
before signing; polling and pagination reuse the same selection. Responses
retain `workspace_id`. Omission/empty selection uses the unique ACTIVE DEFAULT
Workspace. Cross-Workspace Get returns not found; NextToken is Workspace-bound.
Use separate `AGENTKIT_RESOURCE_STATE` files for separate Workspaces.
Update/Delete still locate resources by ID; the server resolves cloud ProjectName.

These scripts call EnvironmentResource through a signed Volcengine/BytePlus TOP
endpoint or a direct endpoint authenticated with an account-scoped API key.

| Script | Action | Purpose |
| --- | --- | --- |
| `01_create_environment_resource.py` | `CreateEnvironmentResource` | Create and optionally wait for `ready` |
| `02_get_environment_resource.py` | `GetEnvironmentResource` | Read a resource or resume polling |
| `03_list_environment_resources.py` | `ListEnvironmentResources` | Filter and traverse `NextToken` pages |
| `04_update_environment_resource.py` | `UpdateEnvironmentResource` | Update metadata or specification with the current Revision |
| `05_delete_environment_resource.py` | `DeleteEnvironmentResource` | Submit deletion and optionally wait for `deleted` |

## Current contract

- Requests use the published TOP JSON contract with recursively PascalCase fields.
- Responses are unwrapped from `Result` and normalized to snake_case internally.
- User-defined `EnvVars` keys retain their exact spelling.
- List uses `MaxResults` and `NextToken`; its result contains `Items` and `NextToken`.
- Create requires `Name`. The script defaults to `AGENTKIT_RESOURCE_NAME` or
  `self-hosted-sandbox-http`.
- Update requires the latest `ExpectedRevision` and an exact `UpdateMask`.
- Delete sends only `ResourceId` and `ClientToken`. Its result contains only
  `ResourceId`; Get supplies progress.
- Resource results no longer contain `Target`, `Spec`, `Components`,
  `LastOperation`, or `ResourceMode`. Current configuration is in `Config` and
  the public failure reason is in `ErrorCode`.
- `ready` is complete only when desired and observed generations match and
  `ErrorCode` is absent. Deletion completes at `deleted`.

## Install

Use `uv`:

```bash
uv venv
uv pip install -r requirements.txt
source .venv/bin/activate
```

## Endpoint configuration

Volcengine:

```bash
export VOLCENGINE_ACCESS_KEY='<access-key>'
export VOLCENGINE_SECRET_KEY='<secret-key>'
export VOLCENGINE_REGION='cn-beijing'
```

PPE:

```bash
export VOLCENGINE_AGENTKIT_HOST='open.volcengineapi.com'
export VOLCENGINE_AGENTKIT_SERVICE='agentkit_ppe'
```

BytePlus:

```bash
export AGENTKIT_CLOUD_PROVIDER='byteplus'
export BYTEPLUS_ACCESS_KEY='<access-key>'
export BYTEPLUS_SECRET_KEY='<secret-key>'
export BYTEPLUS_REGION='ap-southeast-1'
```

Direct mode:

```bash
export MA_RESOURCE_BASE_URL='https://example.internal/environment-resources'
export MA_RESOURCE_API_KEY='<account-scoped-api-key>'
```

Scripts do not load `.env` automatically:

```bash
set -a
source /path/to/.env
set +a
```

## Ark target configuration

```bash
export AGENTKIT_ENVIRONMENT_ID='<environment-id>'
export AGENTKIT_ENVIRONMENT_BASE_URL='https://ark.cn-beijing.volces.com/api/v3'
export AGENTKIT_ENVIRONMENT_KEY='<runtime-secret>'
```

The Environment Key is injected only into Create and Ark specification Update
requests and is never stored in the state file. Ark Create also requires a
Runtime IAM role. Pass an existing role with `--role-name`. On Volcengine TOP,
omitting it searches for a role with `AgentKitDefaultRuntimeAccess`, creating and
attaching the policy when necessary.

## Create

```bash
python 01_create_environment_resource.py \
  --name sandbox-http-demo \
  --description 'temporary verification resource' \
  --client-token create-001 \
  --wait
```

Ark uses the Tool and Runtime `0.0.2` images defined in the script by default.
Optional specification fields include:

```bash
python 01_create_environment_resource.py \
  --sandbox-resources '{"cpu_milli":2000,"memory_mb":4096}' \
  --runtime-resources '{"cpu_milli":2000,"memory_mb":4096}' \
  --sandbox-env-vars '{"LOG_LEVEL":"info"}' \
  --wait
```

A PPE deployment may not yet accept `Runtime.Resources`. Omit
`--runtime-resources` there; the client still implements the current contract.

AgentKit target:

```bash
python 01_create_environment_resource.py \
  --target-type agentkit \
  --name agentkit-resource \
  --wait
```

AgentKit mode omits the Ark Base URL, Environment Key, Runtime, and RoleName. It
also omits Sandbox entirely unless a Sandbox option is explicitly supplied.

## Get and List

```bash
python 02_get_environment_resource.py
python 02_get_environment_resource.py --resource-id er_example --wait ready

python 03_list_environment_resources.py \
  --target-type ark \
  --environment-id "$AGENTKIT_ENVIRONMENT_ID" \
  --max-results 20 \
  --all

python 03_list_environment_resources.py --next-token '<previous-next-token>'
```

List supports `--target-type`, `--environment-id`, `--status`,
`--include-deleted`, `--max-results`, and `--next-token`. It does not modify the
local resource state.

## Update

Update reads ResourceId and the latest Revision from
`.environment_resource_state.json` by default:

```bash
python 04_update_environment_resource.py \
  --name sandbox-http-demo-v2 \
  --description 'updated metadata' \
  --wait

python 04_update_environment_resource.py \
  --sandbox-env-vars '{"LOG_LEVEL":"debug"}' \
  --wait

python 04_update_environment_resource.py \
  --runtime-resources '{"cpu_milli":4000,"memory_mb":8192}' \
  --role-name CustomerRuntimeRole \
  --wait
```

Supported paths are `Name`, `Description`, `Sandbox.ImageUrl`,
`Sandbox.Resources`, `Sandbox.Networking`, `Sandbox.EnvVars`,
`Runtime.Resources`, and `RoleName`. The script generates the PascalCase
`UpdateMask`. Ark specification updates inject the Environment Key; metadata-only
updates do not.

An identical retry must reuse the original client token, ResourceId,
ExpectedRevision, and every request field. Use a new token for a new operation,
after Get refreshes the Revision.

## Delete

```bash
python 05_delete_environment_resource.py --client-token delete-001 --wait
python 02_get_environment_resource.py --wait deleted
```

Delete neither reads nor sends ExpectedRevision. Without an explicit ResourceId,
it reads only the ID from `AGENTKIT_RESOURCE_ID` or the local state file.

## Output, state, and tests

- `--json` emits complete redacted events; the default is a concise Chinese summary.
- `--dry-run` does not access the network, IAM, or state file.
- `AGENTKIT_RESOURCE_STATE` selects an isolated state file. It stores only ID,
  Revision, status, generations, error code, and endpoint.
- `AGENTKIT_WAIT_TIMEOUT_SECONDS` defaults to 1200 seconds;
  `AGENTKIT_POLL_INTERVAL_SECONDS` defaults to 5 seconds.

Run offline tests with:

```bash
uv run --with 'requests>=2.31,<3' \
  python -m unittest discover -s tests -v
```

See [`doc/environment_resource_contract.md`](doc/environment_resource_contract.md)
for the contract source and PPE verification evidence.
