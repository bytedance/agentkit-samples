#!/bin/bash
# Start Volcengine Redis MCP service as a background process

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

if [ -f "volcengine_redis_mcp.pid" ]; then
    echo "Volcengine Redis MCP server is already running with PID $(cat volcengine_redis_mcp.pid)."
    exit 1
fi

LOG_FILE="${LOG_DIR}/volcengine_redis_mcp_$(date +%Y%m%d_%H%M%S).log"

# Use uvx to fetch and run the server from the remote Github repository
# This makes the skill script completely standalone
echo "Starting Volcengine Redis MCP Server..."
nohup uvx --from git+https://github.com/volcengine/mcp-server.git#subdirectory=server/mcp_server_redis mcp-server-redis > "$LOG_FILE" 2>&1 &
PID=$!

echo $PID > volcengine_redis_mcp.pid
echo "Volcengine Redis MCP Server started with PID $PID."
echo "Logs are being written to $LOG_FILE"
