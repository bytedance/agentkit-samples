#!/bin/bash
# Stop the background Volcengine Redis MCP service

if [ ! -f "volcengine_redis_mcp.pid" ]; then
    echo "No volcengine_redis_mcp.pid found. Server is likely not running."
    exit 0
fi

PID=$(cat volcengine_redis_mcp.pid)
if kill -0 $PID > /dev/null 2>&1; then
    echo "Stopping Volcengine Redis MCP server with PID $PID..."
    kill $PID
    sleep 2
    if kill -0 $PID > /dev/null 2>&1; then
        echo "Force killing Volcengine Redis MCP server..."
        kill -9 $PID
    fi
    echo "Volcengine Redis MCP server stopped."
else
    echo "Volcengine Redis MCP server process $PID not found. Cleaning up pid file."
fi

rm volcengine_redis_mcp.pid
