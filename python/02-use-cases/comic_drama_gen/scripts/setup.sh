#!/bin/bash
# install-video-clip-mcp.sh

set -euo pipefail

readonly MCP_PACKAGE="@pickstar-2002/video-clip-mcp@1.2.0"

echo "开始安装 ${MCP_PACKAGE}..."
npm install -g --no-audit --no-fund "${MCP_PACKAGE}"

MCP_BIN="$(command -v video-clip-mcp)"
echo "安装成功，命令路径: ${MCP_BIN}"
