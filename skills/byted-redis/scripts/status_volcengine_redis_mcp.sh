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
