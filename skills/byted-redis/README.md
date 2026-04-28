# Volcengine Redis MCP Skill

This directory contains the Skill implementation for the Volcengine
Redis MCP Server.
It provides a standard interface for intelligent agents
(such as Claude Code) to interact with Volcengine Redis via MCP.

## Structure

- **SKILL.md**: The manifest file for the skill.
  Agents parse this file to understand the skill capabilities and
  usage instructions.
- **scripts/mcp_client.py**: A Python module acting as an MCP client
  for Volcengine Redis.
- **scripts/call_redis_mcp_example.py**: A unified testing and example
  script.
  It lists tools and demonstrates how to invoke both parameterless
  tools (for example, `describe_regions`) and parameterized tools
  (for example, `describe_db_instances`).
- **scripts/start_volcengine_redis_mcp.sh**: Starts the MCP server
  as a background process.
- **scripts/stop_volcengine_redis_mcp.sh**: Stops the background
  MCP server.
- **scripts/status_volcengine_redis_mcp.sh**: Checks the status of
  the background MCP server.

## Installation & Setup

1. Ensure `uv` is installed on your system.
2. Obtain your Volcengine Access Key and Secret Key.
3. Configure `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY`
   in your shell environment before running the client.
4. If needed, set `VOLCENGINE_REGION` as well,
   for example to `cn-beijing`.

## Client Support

This skill is compatible with multiple agent clients:

- **Claude Code**: It will read the `SKILL.md` file and directly
  execute the python scripts using `uv run`.
- **Agentkit**: Can be loaded as a custom MCP skill via standard MCP SDKs.

## Quick Test

```bash
cd skills
uv run scripts/call_redis_mcp_example.py
```
