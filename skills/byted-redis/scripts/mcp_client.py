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

#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


AUTH_ENV_NAMES = (
    "VOLCENGINE_ACCESS_KEY",
    "VOLCENGINE_SECRET_KEY",
    "VOLCENGINE_SESSION_TOKEN",
    "VOLCENGINE_REGION",
    "VOLCENGINE_ENDPOINT",
    "AUTHORIZATION",
    "authorization",
)

RUNTIME_ENV_NAMES = (
    "PATH",
    "HOME",
    "USER",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "SHELL",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "UV_CACHE_DIR",
    "UV_INDEX_URL",
    "UV_EXTRA_INDEX_URL",
    "UV_PYTHON",
)


class RedisMCPClient:
    def __init__(self, env: dict[str, str] | None = None):
        self.session = None
        self._exit_stack = None
        self._env = env

    def _credential_env(self) -> dict[str, str]:
        return self._env if self._env is not None else os.environ

    def _build_server_env(self) -> dict[str, str]:
        server_env = {}
        for name in RUNTIME_ENV_NAMES:
            value = os.environ.get(name)
            if value:
                server_env[name] = value

        for name in AUTH_ENV_NAMES:
            value = self._credential_env().get(name)
            if value:
                server_env[name] = value

        return server_env

    async def connect(self):
        credential_env = self._credential_env()

        # Check credentials. The stdio skill client supports either:
        # 1) AK/SK (optionally with VOLCENGINE_SESSION_TOKEN)
        # 2) AUTHORIZATION / authorization with a Bearer token payload
        has_aksk = bool(
            credential_env.get("VOLCENGINE_ACCESS_KEY")
            and credential_env.get("VOLCENGINE_SECRET_KEY")
        )
        has_authorization = bool(
            credential_env.get("AUTHORIZATION") or credential_env.get("authorization")
        )
        if not has_aksk and not has_authorization:
            print(
                "Error: Missing Redis MCP credentials. Provide either VOLCENGINE_ACCESS_KEY + VOLCENGINE_SECRET_KEY "
                "(optionally with VOLCENGINE_SESSION_TOKEN) or AUTHORIZATION/authorization.",
                file=sys.stderr,
            )
            print(
                "Example 1: define VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY in the environment.",
                file=sys.stderr,
            )
            print(
                "Example 2: define AUTHORIZATION in the environment with a Bearer token.",
                file=sys.stderr,
            )
            sys.exit(1)

        # To support standalone skill distribution without requiring local codebase,
        # we default to using `uvx` to fetch and run the server from the remote repo.
        server_params = StdioServerParameters(
            command="uvx",
            args=[
                "--from",
                "git+https://github.com/volcengine/mcp-server.git#subdirectory=server/mcp_server_redis",
                "mcp-server-redis",
                "-t",
                "stdio",
            ],
            env=self._build_server_env(),
        )

        from contextlib import AsyncExitStack

        self._exit_stack = AsyncExitStack()

        # Start the client
        try:
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
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
            tools.append({"name": t.name, "description": t.description or ""})
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
            if content.type == "text":
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
