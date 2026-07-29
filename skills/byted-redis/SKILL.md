---
name: byted-redis
description: Use this skill only for Volcengine Redis cloud resource operations, including querying, inspecting, creating, or managing Volcengine Redis instances and related cloud resources. Trigger it when the user mentions Volcengine Redis, Volcengine Redis instances, Volcengine Redis inventory/detail lookup, Volcengine Redis operational metadata, or Volcengine Redis MCP/OpenAPI access.
version: 1.1.1
license: Apache-2.0
---

# Volcengine Redis MCP Server Skill

## Purpose

Use this skill as the agent-facing workflow for Volcengine Redis cloud resource operations. The skill bundles MCP client scripts, startup scripts, credential guidance, and tool-selection instructions so agents can perform Volcengine Redis resource queries and management tasks.

This skill is scoped to Volcengine Redis only. Redis-related requests outside Volcengine, such as OSS Redis command execution, self-hosted Redis troubleshooting, application cache logic, Redis running in Kubernetes, or non-Volcengine cloud Redis products, should use other tools or skills.

## Triggering Rules

Use this skill when the user asks for Volcengine Redis tasks such as:

- Redis instance inventory, detail lookup, status lookup, filtering by region, instance ID, name, tag, VPC, or subnet.
- Region, zone, VPC, subnet, EIP, spec, shard, node ID, endpoint, bandwidth, or topology information.
- Slow log, hot key, big key, key scan job, planned event, or operational metadata queries.
- Backup, PITR, cross-region backup, backup plan, or backup download URL queries.
- Parameter group, instance parameter, ACL command/category, account, or allowlist operations.
- Creating or modifying Volcengine Redis resources, including instances, accounts, allowlists, public endpoints, names, and parameters.

Do not use this skill for generic Redis command execution against a data endpoint, application-side cache debugging, Kubernetes pod metadata lookup, self-hosted Redis, other cloud providers' Redis products, or any non-Volcengine Redis resource unless the user explicitly says the target is Volcengine Redis.

## Execution Workflow

1. Classify the request as read-only or mutating.
2. Check the required identifiers. Prefer explicit `region_id` and `instance_id` when available. If the user gives only a name or vague keyword, first call `describe_db_instances` with region and filter arguments, then use the returned instance ID for detail tools.
3. Verify credentials are available before starting MCP:
   - `AUTHORIZATION` or `authorization`, or
   - `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY`, with optional `VOLCENGINE_SESSION_TOKEN`.
4. If the region is not supplied, use `VOLCENGINE_REGION` when set. If neither the user nor the environment gives a region, ask for the region before making region-scoped calls. Prefer region-scoped discovery tools such as `describe_zones` or `describe_db_instances` once the region is known.
5. Use the bundled client in `scripts/mcp_client.py` for custom calls. For a smoke test, run `uv run scripts/call_redis_mcp_example.py` from this skill directory.
6. For mutating operations, summarize the target resource and intended change, then ask for user confirmation before calling the tool unless the user has already clearly authorized that exact mutation.
7. Return concise results with the resource identifiers, region, status, and the fields relevant to the user's question. Mention when output was filtered or truncated.

## Credentials

The bundled stdio client supports two credential modes.

### Environment AK/SK

Use these variables:

- `VOLCENGINE_ACCESS_KEY`
- `VOLCENGINE_SECRET_KEY`
- `VOLCENGINE_REGION`, for example `cn-beijing`

For temporary credentials, also use:

- `VOLCENGINE_SESSION_TOKEN`

### Authorization Bearer Token

Use `AUTHORIZATION` or `authorization` with this format:

```http
Authorization: Bearer BASE64_JSON_PAYLOAD
```

The decoded JSON payload should contain:

- `AccessKeyId`
- `SecretAccessKey`
- `SessionToken`
- `CurrentTime`
- `ExpiredTime`
- `Region`

`SessionToken` is required for STS credentials. Authorization credentials take precedence over environment AK/SK when both are present.

Never print full secrets, AK/SK values, session tokens, or authorization payloads. If a credential check is needed, report only whether each variable is present.

## Tool Selection

Use read-only tools by default. The table below is a routing guide, not a closed capability list. The upstream MCP server is the source of truth for the currently available tools. If the server exposes new tools later, agents can call them through the same `RedisMCPClient.call_tool(name, arguments)` flow after checking the tool name, schema, and safety level.

| User intent | Preferred tool | Key arguments |
| --- | --- | --- |
| List regions | `describe_regions` | only when supported by the live server schema; otherwise provide `region_id` or use another region-scoped discovery tool |
| List zones | `describe_zones` | `region_id` |
| List VPCs or subnets | `describe_vpcs`, `describe_subnets` | `region_id`, optional VPC/subnet filters |
| Find Redis instances | `describe_db_instances` | `region_id`, optional `instance_id`, `instance_name`, paging/filter fields |
| Inspect one instance | `describe_db_instance_detail` | `region_id`, `instance_id` |
| Query specs | `describe_db_instance_specs` | `region_id`, optional zone/spec filters |
| Query shards or nodes | `describe_db_instance_shards`, `describe_node_ids` | `region_id`, `instance_id` |
| Slow logs, hot keys, big keys | `describe_slow_logs`, `describe_hot_keys`, `describe_big_keys` | `region_id`, `instance_id`, time range when supported |
| Backups and PITR | `describe_backups`, `describe_backup_plan`, `describe_pitr_time_window` | `region_id`, `instance_id` |
| Parameters | `describe_db_instance_params`, `describe_parameter_groups`, `describe_parameter_group_detail` | `region_id`, `instance_id` or parameter group ID |
| Accounts | `list_db_account` | `region_id`, `instance_id` |
| Allowlists | `describe_allow_lists`, `describe_allow_list_detail` | `region_id`, optional allowlist ID |
| Tags | `describe_tags_by_resource` | `region_id`, resource type and resource IDs |
| Events and scans | `describe_planned_events`, `describe_key_scan_jobs` | `region_id`, `instance_id` when supported |

Use mutating tools only after confirmation:

- `create_db_instance`
- `modify_db_instance_params`
- `create_db_account`
- `create_allow_list`
- `associate_allow_list`
- `disassociate_allow_list`
- `modify_db_instance_name`
- `create_parameter_group`
- `create_db_endpoint_public_address`

## Argument Guidance

The upstream server tool schemas are the source of truth. Before calling an unfamiliar tool, list tools or inspect the tool schema through the MCP client if the active client exposes schemas.

General conventions:

- Prefer argument names shown by the upstream MCP schema. Common examples include `region_id`, `instance_id`, `instance_name`, and `page_size`.
- Keep page sizes small for exploratory calls, commonly `page_size: 10` or less. Increase only when the user asks for a full inventory.
- Include time windows for logs and key analysis whenever the tool supports them. Ask for a time range if the user's requested time scope is ambiguous and the query could be expensive.
- For instance lookup by name, first call `describe_db_instances`, handle zero or multiple matches explicitly, and only then call detail tools.
- For downloaded backup URLs or public endpoint creation, treat the result as sensitive operational output and summarize carefully.

## Client Usage

Run commands from the skill directory:

```bash
uv run scripts/call_redis_mcp_example.py
```

For one-off calls, use the bundled client:

```python
import asyncio
import sys

sys.path.append("scripts")
from mcp_client import RedisMCPClient

async def main():
    async with RedisMCPClient() as client:
        result = await client.call_tool(
            "describe_db_instances",
            {"region_id": "cn-beijing", "page_size": 10},
        )
        print(result)

asyncio.run(main())
```

The service scripts are optional and run the server as a background `streamable-http` service. They do not affect the normal stdio client path:

```bash
./scripts/start_volcengine_redis_mcp.sh
./scripts/status_volcengine_redis_mcp.sh
uv run scripts/call_redis_mcp_streamable_http_example.py
./scripts/stop_volcengine_redis_mcp.sh
```

The background service inherits credentials and region only from the environment present at service startup. If credential or region environment variables change after startup, restart the background service before reusing the HTTP example script.

`status_volcengine_redis_mcp.sh` reports the credential mode captured at startup. `Health: READY` only means the HTTP endpoint is alive; Redis tool calls can still fail if the service was started without credentials.

For normal agent execution, prefer the stdio client because it starts and stops the server for the individual call path.

## Failure Handling

Use this checklist when a call fails:

- Missing credentials: report the missing credential mode and ask the user to provide either AK/SK or `AUTHORIZATION`. Do not continue with anonymous calls.
- Expired STS: ask the user for a fresh token if the error mentions expiration, invalid session token, or invalid security token.
- Missing region: ask for region before calling region-scoped discovery or detail tools. Do not assume `describe_regions` can be called without a region unless the live server schema confirms it.
- No instance found: return the filters used and ask whether to broaden the query.
- Multiple instances found: show the candidate instance IDs, names, regions, and statuses, then ask which one to use for destructive or detail-sensitive operations.
- Permission denied: identify the failed API/tool and the target resource. Suggest checking Redis, VPC, EIP, or IAM permissions depending on the tool.
- MCP server startup failure: check `uv`, network access, package resolution, Python version, and proxy settings.
- Schema or argument error: list the intended tool, arguments used, and retry after aligning argument names with the upstream tool schema.
- Rate limits or transient API errors: retry read-only calls once if appropriate. Do not retry mutating calls unless idempotency is clear.

## Output Expectations

When reporting results, include:

- Region and instance ID whenever applicable.
- Instance name, status, engine version, topology, shard/node summary, network/VPC information, and tags when relevant.
- Time range for logs, hot key, big key, backup, or event queries.
- Any ambiguity, truncation, or follow-up identifier needed for the next operation.

For mutating operations, include the requested change, final API response status, and resource identifiers. Do not claim success unless the MCP tool returns a successful result.
