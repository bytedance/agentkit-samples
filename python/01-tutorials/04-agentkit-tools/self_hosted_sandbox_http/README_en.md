# Self-hosted Sandbox: EnvironmentResource HTTP examples

[简体中文](README.md)

Create, get, list, update and delete an `EnvironmentResource` group through HTTP. A group manages a Sandbox Tool and optionally an ACTB dispatcher Runtime for an existing Environment. These examples require only `requests`, without the AgentKit SDK.

| Script | Action | Purpose |
| --- | --- | --- |
| `01_create_environment_resource.py` | `CreateEnvironmentResource` | Submit creation; optionally `--wait` for readiness |
| `02_get_environment_resource.py` | `GetEnvironmentResource` | Read status, revision and components; resume polling |
| `03_list_environment_resources.py` | `ListEnvironmentResources` | Filter, fetch a page, or traverse pages with `--all` |
| `04_update_environment_resource.py` | `UpdateEnvironmentResource` | Update metadata or sandbox settings with a generated `update_mask` |
| `05_delete_environment_resource.py` | `DeleteEnvironmentResource` | Delete owned components; optionally wait for the tombstone |

## 1. Install and configure the API endpoint

Use Python 3.10+ and run from this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**The default transport is TOP OpenAPI with AK/SK signing.** All five Actions must be registered and published on the selected platform. Backend implementation alone does not guarantee availability in every region or platform.

```bash
export AGENTKIT_CLOUD_PROVIDER=volcengine
export VOLCENGINE_ACCESS_KEY='<your-access-key>'
export VOLCENGINE_SECRET_KEY='<your-secret-key>'
export VOLCENGINE_AGENTKIT_REGION=cn-beijing
# Optional endpoint where these Actions have been published:
# export VOLCENGINE_AGENTKIT_HOST='<openapi-host-without-scheme>'
# export VOLCENGINE_AGENTKIT_SERVICE=agentkit
```

The default request is `POST https://open.volcengineapi.com/?Action=<Action>&Version=2025-10-30`. JSON fields remain `snake_case`; successful responses may be plain resource objects / `data` lists or wrapped in `Result`. Signing does not determine the response envelope.

If your deployment exposes direct routes and accepts an account-scoped API key, select direct HTTP explicitly:

```bash
export MA_RESOURCE_BASE_URL='https://<your-ma-infra-endpoint>'
export MA_RESOURCE_API_KEY='<account-scoped-api-key>'
```

`MA_RESOURCE_BASE_URL` takes precedence: requests go to `POST <base-url>/<Action>` with `x-api-key`, returning a plain JSON object without AK/SK signing or a `Result` envelope. Use the endpoint and authentication supported by your deployment. The examples do not inject trusted gateway account headers. To return to TOP, run `unset MA_RESOURCE_BASE_URL MA_RESOURCE_API_KEY`.

BytePlus signing configuration is also retained; availability of these Actions must be confirmed separately:

```bash
export AGENTKIT_CLOUD_PROVIDER=byteplus
export BYTEPLUS_ACCESS_KEY='<your-access-key>'
export BYTEPLUS_SECRET_KEY='<your-secret-key>'
export BYTEPLUS_AGENTKIT_REGION=ap-southeast-1
# Default host: agentkit.ap-southeast-1.byteplusapi.com
# export BYTEPLUS_AGENTKIT_HOST='<published-openapi-host>'
```

For temporary credentials, use `VOLCENGINE_SESSION_TOKEN` / `BYTEPLUS_SESSION_TOKEN`. Override the signing service and API version with `VOLCENGINE_AGENTKIT_SERVICE` and `VOLCENGINE_AGENTKIT_API_VERSION`, or their `BYTEPLUS_` equivalents.

## 2. Create a self-host resource group

The default `target.type=ark` creates a Sandbox Tool and an ACTB dispatcher Runtime for an existing external Environment.

| Option | Ark default |
| --- | --- |
| `--target-type` | `ark` (overridable with `AGENTKIT_RESOURCE_TARGET`) |
| `--sandbox-image` | `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:tool-ark-skills-0.0.2` |
| `--runtime-image` | `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:runtime-ark-skills-0.0.2` |

After configuring the required Environment settings below and authentication above, run `python 01_create_environment_resource.py` directly. All creation CLI arguments are optional. An omitted `--client-token` is generated and printed; unconfigured name, description, region, env_vars and Skill Space fields are omitted.

```bash
export AGENTKIT_RESOURCE_TARGET=ark
export AGENTKIT_ENVIRONMENT_ID='<existing-environment-id>'
export AGENTKIT_ENVIRONMENT_BASE_URL='https://<external-environment-api>'
export AGENTKIT_ENVIRONMENT_KEY='<environment-data-plane-key>'
# Optional Skill Space owned by the current account:
# export AGENTKIT_SKILL_SPACE_ID='<skill-space-id>'

# Preview without credentials; --json shows the full redacted request body
python 01_create_environment_resource.py --dry-run --json

# Submit and wait; omit --wait to exit after the submission response
python 01_create_environment_resource.py --wait
```

The request body has the following shape. `target.environment_key` is distinct from control-plane AK/SK credentials and the account-scoped API key:

```json
{
  "client_token": "<automatically-generated-token>",
  "resource_mode": "runtime_and_sandbox",
  "target": {
    "type": "ark",
    "environment_id": "env_example",
    "base_url": "https://external.example.com",
    "environment_key": "<environment-data-plane-key>"
  },
  "sandbox": {
    "profile": "ark_skills",
    "image_url": "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:tool-ark-skills-0.0.2"
  },
  "runtime": {"image_url": "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:runtime-ark-skills-0.0.2"}
}
```

Override the Ark defaults with `--sandbox-image` and `--runtime-image`. Pass an empty string explicitly to omit the corresponding image field and use the server default. AgentKit mode continues to use the server Sandbox image by default and omits Runtime. The Runtime image must be an ACTB self-host dispatcher. Tool environment variables use `--sandbox-env-vars '{"APP_MODE":"demo"}'` or `--sandbox-env-vars @env-vars.json`, with string values only. `--skill-space-id` populates `sandbox.env_vars.SKILL_SPACE_ID`. The resource-group contract does not accept packages or RuntimeTemplate parameters.

To create only an AgentKit Sandbox:

```bash
export AGENTKIT_RESOURCE_TARGET=agentkit
export AGENTKIT_ENVIRONMENT_ID='<existing-agentkit-cloud-environment-id>'
python 01_create_environment_resource.py --wait
```

This sends `resource_mode=sandbox_only` and `sandbox.profile=ma_infra`, omitting `runtime` and the external Environment Key. The target must be an unarchived cloud Environment owned by the account, with a ready account Endpoint and no active resource group or binding. Normal cloud Environment creation may already create a group automatically; check List first.

## 3. Get and list

```bash
# Use the resource_id saved by the latest Create/Get/Update/Delete
python 02_get_environment_resource.py
python 02_get_environment_resource.py --wait ready

# Query any known resource independently
python 02_get_environment_resource.py --resource-id er_example

# No options sends {}, using server pagination defaults
python 03_list_environment_resources.py
python 03_list_environment_resources.py --target-type ark --limit 20 --all
python 03_list_environment_resources.py --environment-id "$AGENTKIT_ENVIRONMENT_ID" --include-deleted
python 03_list_environment_resources.py --target-type ark --page '<previous-next_page>'
```

List filters include `--target-type`, `--environment-id`, `--resource-mode`, `--status` and `--include-deleted`. `--limit` accepts 1–100. `--all` prints each page and follows `next_page`; keep the account and filters unchanged when continuing manually. List does not overwrite the current resource cache.

## 4. Update

Update reads `resource_id` and `revision` from `.environment_resource_state.json` by default, sending the latter as `expected_revision`. No manual ID or version is needed. Create/Get/Update/Delete refresh this file after receiving a resource response. Run Get first when you need the latest server revision.

```bash
python 02_get_environment_resource.py
python 04_update_environment_resource.py \
  --name 'renamed-sandbox' --description 'HTTP example' --wait

# Use the revision saved to JSON by the previous operation
python 04_update_environment_resource.py \
  --sandbox-image 'registry.example.com/sandbox:v2' \
  --sandbox-env-vars '{"APP_MODE":"updated"}' --wait
```

Replace the image with a real, pullable image. Metadata updates finish synchronously. Sandbox specification updates enter `updating` and replace components asynchronously. Ark specification updates require `AGENTKIT_ENVIRONMENT_KEY` again; the script injects `target.environment_key` only for this case. Use `--target-type agentkit` or `AGENTKIT_RESOURCE_TARGET=agentkit` for AgentKit specification updates.

| Option | `update_mask` path | Meaning |
| --- | --- | --- |
| `--name` | `name` | Rename |
| `--description` / `--clear-description` | `description` | Set text / clear with `null` |
| `--sandbox-image` | `sandbox.image_url` | Replace the Sandbox image |
| `--sandbox-env-vars` | `sandbox.env_vars` | Replace custom variables; `'{}'` clears them, including Skill Space settings |
| `--sandbox-resources` | `sandbox.resources` | JSON object or `@file.json` |
| `--sandbox-networking` | `sandbox.networking` | JSON object or `@file.json`; existing environment policies still apply |

Values remain at their original field locations, for example `{"update_mask":["sandbox.env_vars"],"sandbox":{"env_vars":{}}}`. Target, region, mode and profile are immutable.

## 5. Delete

Drain workloads in the external Environment and ensure the resources are no longer in use. Get can refresh the local JSON before deletion. The delete script reads the ID and revision from that file automatically:

```bash
python 02_get_environment_resource.py
python 05_delete_environment_resource.py --wait

# Deleted resources remain queryable as tombstones
python 02_get_environment_resource.py --wait deleted
python 03_list_environment_resources.py --include-deleted --all
```

Deletion removes owned Runtime components before the Tool. Historical `ownership=referenced` components are retained, as is the target Environment. Local resources with non-terminated Sessions, unfinished Work or sandbox creation intents return `ResourceInUse`.

## Output example

A newly accepted creation request produces a summary like this (example ID):

```text
[已受理] 创建请求已提交，尚未确认操作完成。
资源 ID: er_example
当前状态: 创建中 (creating)
当前版本 (revision): 1
状态已保存: .../.environment_resource_state.json
继续等待: python 02_get_environment_resource.py --resource-id er_example --wait ready
```

With `--wait`, confirmed completion prints `[成功] 环境资源创建成功。` (creation succeeded). Failures print `[失败]` and their reason; HTTP 200 alone is not treated as successful provisioning. For complete details such as component history:

```bash
python 02_get_environment_resource.py --json
```

## Status, retries and configuration

- By default, scripts print a concise Chinese summary: progress, accepted/succeeded/failed result, resource ID, status, revision, available Tool/Runtime IDs and the state-file path. Failures show their error code directly. Success is shown only after completion is confirmed; asynchronous submissions first show “已受理” (accepted). List prints one row per resource with counts and pagination hints.
- Every script supports `--json` for full redacted events (`request`, `response`, `poll`, `completed`, or `page` for List), without mixing the human summary into that output. `--dry-run` previews without network access or state writes.
- Waiting for creation or specification updates requires `ready`, `last_operation.status=completed` and matching desired/observed generations. Metadata operations require a ready resource and a completed operation without generation convergence. A rolled-back `ready + failed_clean` fails the command. Deletion requires `deleted` and a completed operation. Inspect `last_operation` and `components.history` after failures.
- Create, update and delete all accept an optional `--client-token`; when omitted, a token is generated and printed for that invocation. **For an identical retry, pass `--client-token <previously-printed-token>` and preserve the resource_id, expected_revision and every request parameter.** Automatic HTTP retries reuse the token and request body without refreshing the revision. If the state JSON has changed before a manual retry, explicitly pass the original `--resource-id` and `--expected-revision` as well. Running create, update or delete again without a token starts a new operation. After `RevisionConflict`, Get first and decide whether to submit a new operation with a new token.
- Ark creation/specification-update keys exist only for the request and the server's in-process operation. After a server restart, resume unfinished work by resending the original token, parameters and key. Get alone does not resubmit the key.
- Polling timeout does not cancel server operations. Resume with `02_get_environment_resource.py --wait ready` or `--wait deleted`. After resolving an external cause of `delete_failed`, start a new deletion with a new token and the latest revision.

| Environment variable | Default / purpose |
| --- | --- |
| `AGENTKIT_RESOURCE_ID` | Explicit resource selection; below `--resource-id`, above the cache |
| `AGENTKIT_RESOURCE_STATE` | `.environment_resource_state.json` in this directory; IDs, revision, status, generations and endpoint only, without keys, requests or env_vars |
| `AGENTKIT_RESOURCE_TARGET` | Create/Update default to `ark`; optionally `agentkit`. List defaults to all targets |
| `AGENTKIT_WAIT_TIMEOUT_SECONDS` | 1200 seconds |
| `AGENTKIT_POLL_INTERVAL_SECONDS` | 5 seconds |
| `AGENTKIT_HTTP_TIMEOUT_SECONDS` | 30 seconds per HTTP request |
| `AGENTKIT_HTTP_RETRIES` | Up to 2 retries for connection failures and HTTP 429/503, preserving the body |

ID precedence is `--resource-id` → `AGENTKIT_RESOURCE_ID` → JSON. Revision precedence is `--expected-revision` → JSON `revision` (not `runtime_version`). A selected ID that differs from the cached ID cannot reuse the cached revision: Get that resource first or pass the revision explicitly. Missing state, an invalid revision or a different endpoint fails before any request. Select another state file with `AGENTKIT_RESOURCE_STATE=/path/to/resource.json`. Use separate files or explicit ID and revision together when switching accounts or working with multiple resources. Output redacts Environment Keys, credentials and env_vars values. Every script supports `--help`.

## Local validation

```bash
python -m unittest discover -s tests -v
```

Tests use a local mock HTTP server to check paths, signing headers, response envelopes, retry parameters, pagination, asynchronous completion and redaction. They do not access cloud services. On 2026-09-24, read-only List/Get calls to live Volcengine TOP confirmed plain responses and verified the corrected Get parser. This does not establish successful provisioning; full cloud lifecycle and BytePlus integration remain unverified. See the [source contract notes](doc/environment_resource_contract.md) for evidence and validation boundaries.

## Troubleshooting response parsing and asynchronous failures

If an older script reports `TOP response is missing a JSON object Result`, the request may already have been accepted. The parser now supports resource JSON forwarded directly through TOP. First find the resource with `03_list_environment_resources.py --environment-id <environment-id>`, then inspect it with `02_get_environment_resource.py --resource-id <resource-id>`. Avoid starting a new creation without the original token. Unknown response shapes still fail with top-level field names; arbitrary HTTP 200 objects are not treated as success.

For a resource in `failed`, inspect `last_operation.error_code` and `components.history`. For example, `Provider.InvalidParameter.RoleName` means a downstream component-creation request rejected RoleName, independently of local JSON parsing. The Ark Tool RoleName comes from the server's `MA_RUNTIME_ROLE_NAME`; check the deployed value and the role in the target account. Adding an undeclared field to the creation request does not fix it.
