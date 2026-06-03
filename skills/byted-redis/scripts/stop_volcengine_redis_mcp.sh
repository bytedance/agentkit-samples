# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
