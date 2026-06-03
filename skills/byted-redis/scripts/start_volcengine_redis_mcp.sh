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
nohup uvx --from git+https://github.com/volcengine/mcp-server.git#subdirectory=server/mcp_server_redis mcp-server-redis -t stdio > "$LOG_FILE" 2>&1 &PID=$!

echo $PID > volcengine_redis_mcp.pid
echo "Volcengine Redis MCP Server started with PID $PID."
echo "Logs are being written to $LOG_FILE"
