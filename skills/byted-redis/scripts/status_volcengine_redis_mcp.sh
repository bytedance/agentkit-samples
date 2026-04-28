#!/bin/bash
# Check the status of the Volcengine Redis MCP service

if [ ! -f "volcengine_redis_mcp.pid" ]; then
    echo "Status: STOPPED (volcengine_redis_mcp.pid not found)"
    exit 0
fi

PID=$(cat volcengine_redis_mcp.pid)
if kill -0 $PID > /dev/null 2>&1; then
    echo "Status: RUNNING (PID: $PID)"
    echo "Recent logs:"
    ls -t logs/volcengine_redis_mcp_*.log | head -1 | xargs tail -n 10
else
    echo "Status: STOPPED (PID file exists but process $PID is not running)"
    rm volcengine_redis_mcp.pid
fi
