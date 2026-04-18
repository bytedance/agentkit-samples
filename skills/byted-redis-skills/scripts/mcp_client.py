#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class RedisMCPClient:
    def __init__(self):
        self.session = None
        self._exit_stack = None

    async def connect(self):
        # Set up the server parameters
        env = os.environ.copy()
        
        # Check required credentials
        required_vars = ["VOLCENGINE_ACCESS_KEY", "VOLCENGINE_SECRET_KEY"]
        missing_vars = [var for var in required_vars if var not in env]
        if missing_vars:
            print(f"Error: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
            print("Please set them using: export VOLCENGINE_ACCESS_KEY='...' export VOLCENGINE_SECRET_KEY='...'", file=sys.stderr)
            sys.exit(1)

        # To support standalone skill distribution without requiring local codebase,
        # we default to using `uvx` to fetch and run the server from the remote repo.
        server_params = StdioServerParameters(
            command="uvx",
            args=[
                "--from",
                "git+https://github.com/volcengine/mcp-server.git#subdirectory=server/mcp_server_redis",
                "mcp-server-redis"
            ],
            env=env
        )

        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        
        # Start the client
        try:
            read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
            self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
        except Exception as e:
            print(f"Failed to connect to MCP server: {e}", file=sys.stderr)
            sys.exit(1)

    async def list_tools(self):
        """List all available tools."""
        if not self.session:
            raise RuntimeError("Client not connected")
        result = await self.session.list_tools()
        tools = []
        for t in result.tools:
            tools.append({
                "name": t.name,
                "description": t.description
            })
        return tools

    async def call_tool(self, name: str, arguments: dict = None):
        """Call a specific tool."""
        if not self.session:
            raise RuntimeError("Client not connected")
        arguments = arguments or {}
        result = await self.session.call_tool(name, arguments)
        
        # Parse text content from response
        output = ""
        for content in result.content:
            if content.type == 'text':
                output += content.text + "\n"
        return output

    async def close(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
            self.session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
