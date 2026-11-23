"""MCP 服务配置与启动入口，默认监听 0.0.0.0:8000，路径为 /mcp。"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mcp_tool import call_remote_agent


load_dotenv(Path(__file__).with_name(".env"))

mcp = FastMCP(
    name="remote_agent_mcp",
    instructions="使用 remote_agent_poc_hiagent 工具，将用户消息交给远程 Agent 处理。",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8000")),
    stateless_http=True,
    json_response=True,
)
mcp.add_tool(call_remote_agent, name="remote_agent_poc_hiagent")

app = mcp.streamable_http_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将远程 A2A Agent 暴露为 MCP 工具")
    parser.add_argument(
        "--transport",
        choices=("streamable-http", "stdio"),
        default="streamable-http",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)
