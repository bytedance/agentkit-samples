# Volcengine Redis MCP Skill

This directory contains the Skill implementation for the Volcengine Redis MCP Server. It provides a standard interface for intelligent agents (such as Claude Code) to interact with Volcengine Redis via MCP.

## Structure

- **SKILL.md**: The manifest file for the skill. Agents parse this file to understand the skill capabilities and usage instructions.
- **scripts/mcp_client.py**: A Python module acting as an MCP client for Volcengine Redis.
- **scripts/call_redis_mcp_example.py**: A unified testing and example script. It lists tools and demonstrates how to invoke both parameterless tools (e.g., `describe_regions`) and parameterized tools (e.g., `describe_db_instances`).
- **scripts/start_volcengine_redis_mcp.sh**: Starts the MCP server as a background process.
- **scripts/stop_volcengine_redis_mcp.sh**: Stops the background MCP server.
- **scripts/status_volcengine_redis_mcp.sh**: Checks the status of the background MCP server.

## Installation & Setup

1. Ensure `uv` is installed on your system.
2. Prepare one of the following Volcengine credential modes.

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
cd skills
uv run scripts/call_redis_mcp_example.py
```
