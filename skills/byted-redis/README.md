# Volcengine Redis MCP Skill

This directory contains the agent-facing Skill for Volcengine Redis cloud resource operations. It provides trigger guidance, credential handling, MCP client scripts, service management scripts, and examples for intelligent agents to interact with Volcengine Redis.

This skill is only for Volcengine Redis resource operations. It should not be used for generic Redis command execution, self-hosted Redis, Kubernetes Redis pods, application cache debugging, or Redis services from other cloud providers unless the user explicitly says the target is Volcengine Redis.

## Structure

- **SKILL.md**: The manifest file for the skill. Agents parse this file to understand the skill capabilities and usage instructions.
- **scripts/mcp_client.py**: A Python module acting as an MCP client for Volcengine Redis.
- **scripts/call_redis_mcp_example.py**: A unified testing and example script. It lists tools and demonstrates how to invoke stable region-scoped discovery tools (for example `describe_zones`) and parameterized tools (for example `describe_db_instances`).
- **scripts/call_redis_mcp_streamable_http_example.py**: A validation script for the background `streamable-http` MCP service. It connects to the configured HTTP endpoint and runs a read-only Redis tool call.
- **scripts/background_streamable_http_mcp_service.py**: The Python helper behind the background service lifecycle commands. It manages `start`, `status`, and `stop` for the `streamable-http` transport.
- **scripts/start_volcengine_redis_mcp.sh**: Starts the MCP server as a background `streamable-http` service.
- **scripts/stop_volcengine_redis_mcp.sh**: Stops the background `streamable-http` service.
- **scripts/status_volcengine_redis_mcp.sh**: Checks the status and TCP readiness of the background `streamable-http` service.

## Agent Workflow

Agents should follow the detailed workflow in `SKILL.md`. In short:

1. Trigger this skill only for Volcengine Redis resource queries or management tasks.
2. Classify the request as read-only or mutating.
3. Verify credentials and region before making region-scoped calls.
4. Prefer read-only discovery tools first, such as `describe_zones` and `describe_db_instances`, once a region is known.
5. Resolve ambiguous instance names to explicit instance IDs before calling detail or mutation tools.
6. Ask for user confirmation before using mutating tools.
7. Summarize results with region, instance ID, status, and relevant operational fields.

Mutating tools include instance creation, parameter modification, account creation, allowlist changes, endpoint creation, parameter group creation, and instance rename operations.

The tool examples in `SKILL.md` are a routing guide. Agents should treat the MCP server's live tool list and schemas as the source of truth, so newly added upstream tools can be called through the same MCP client flow after checking their schema and safety level.

## Installation & Setup

1. Ensure `uv` is installed on your system.
2. Ensure network access or a configured `uv` source that can fetch MCP server dependencies.
3. Prepare one of the following Volcengine credential modes.

### Option A: Static AK/SK or temporary credentials via environment variables (stdio)

Prepare these environment variables in your terminal or secret manager before starting the skill:

- `VOLCENGINE_ACCESS_KEY`
- `VOLCENGINE_SECRET_KEY`
- `VOLCENGINE_REGION` (for example `cn-beijing`)

If you are using temporary credentials, also prepare:

- `VOLCENGINE_SESSION_TOKEN`

### Option B: STS credentials via `Authorization` / `authorization` (stdio or HTTP clients)

You can also pass a Bearer token whose body is a Base64-encoded JSON payload through the `Authorization` header.

The decoded JSON should contain these fields:

- `AccessKeyId`
- `SecretAccessKey`
- `SessionToken`
- `CurrentTime`
- `ExpiredTime`
- `Region`

Notes:

- `SessionToken` is required when using STS.
- If both `CurrentTime` and `ExpiredTime` are present, the server validates whether the STS token is expired.
- For the provided stdio skill scripts, you may export the token through `AUTHORIZATION` or `authorization`.
- If both header/authorization credentials and environment AK/SK are provided, authorization credentials take precedence.

## Client Support

This skill is compatible with multiple agent clients:
- **Claude Code**: It will read the `SKILL.md` file and directly execute the python scripts using `uv run`.
- **Agentkit**: Can be loaded as a custom MCP skill via standard MCP SDKs.

## Quick Test

```bash
cd skills/byted-redis
uv run scripts/call_redis_mcp_example.py
```

The smoke test:

- starts the Redis MCP server through stdio
- lists available MCP tools
- calls `describe_zones` with the resolved region
- calls `describe_db_instances` with a small page size

## Background Service

The background scripts use the MCP server's `streamable-http` transport. This keeps the daemon path separate from the normal stdio client path used by `scripts/mcp_client.py`.

The background service scripts are intended for POSIX-like shell environments such as macOS and Linux. On other systems, use the stdio client path.

Default endpoint:

- `http://127.0.0.1:18765/mcp`

Optional overrides:

- `VOLCENGINE_REDIS_MCP_HOST`
- `VOLCENGINE_REDIS_MCP_PORT`

Commands:

```bash
cd skills/byted-redis
./scripts/start_volcengine_redis_mcp.sh
./scripts/status_volcengine_redis_mcp.sh
uv run scripts/call_redis_mcp_streamable_http_example.py
./scripts/stop_volcengine_redis_mcp.sh
```

Credential note for the background service:

- The background `streamable-http` server inherits credentials and region only from the environment present when `./scripts/start_volcengine_redis_mcp.sh` is executed.
- If you change credential or region environment variables after the server has already started, restart the background service before rerunning the HTTP example.
- `./scripts/status_volcengine_redis_mcp.sh` reports the credential mode captured at startup. `Health: READY` only means the HTTP endpoint is alive; it does not mean Redis credentials were available to the background service.

## Troubleshooting

- Missing credentials: provide either `VOLCENGINE_ACCESS_KEY` + `VOLCENGINE_SECRET_KEY`, or `AUTHORIZATION` / `authorization`.
- Expired STS: refresh the authorization token or temporary session token.
- Missing region: set `VOLCENGINE_REGION` or pass `region_id` in the tool arguments before calling region-scoped discovery or detail tools.
- MCP server startup failure: check network/proxy settings, `uv` installation, and package resolution.
- Tool argument errors: inspect the upstream MCP tool schema and prefer the argument names described in `SKILL.md`, such as `region_id`, `instance_id`, and `page_size`.
- Permission denied: check Volcengine IAM permissions for Redis and related VPC/EIP resources.
