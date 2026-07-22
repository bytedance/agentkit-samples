#!/usr/bin/env python3
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

#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
import json
import os
import sys
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def endpoint() -> str:
    host = os.getenv("VOLCENGINE_REDIS_MCP_HOST", "127.0.0.1")
    port = os.getenv("VOLCENGINE_REDIS_MCP_PORT", "18765")
    return f"http://{host}:{port}/mcp"


def extract_text_content(result: Any) -> str:
    parts = []
    for item in getattr(result, "content", []):
        if getattr(item, "type", None) == "text":
            parts.append(item.text)
    return "".join(parts).strip()


async def main() -> None:
    region = os.getenv("VOLCENGINE_REGION", "cn-beijing")
    url = endpoint()
    failure_message: str | None = None

    print("Testing Volcengine Redis MCP streamable-http server...")
    print(f"Resolved endpoint: {url}")
    print(f"Resolved region for requests: {region}")

    try:
        async with streamable_http_client(url) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("\n1. Successfully connected to the streamable-http MCP server.")

                tools = await session.list_tools()
                print(f"\n2. Retrieved {len(tools.tools)} tools:")
                for tool in tools.tools[:5]:
                    desc = (tool.description or "")[:60]
                    print(f"  - {tool.name}: {desc}...")
                if len(tools.tools) > 5:
                    print(f"  ... and {len(tools.tools) - 5} more tools.")

                print("\n3. Testing tool invocation: describe_zones (with args)")
                result = await session.call_tool(
                    "describe_zones",
                    {"region_id": region},
                )
                raw = extract_text_content(result)
                if getattr(result, "isError", False) or "Error executing tool" in raw:
                    failure_message = raw or "describe_zones returned an unknown MCP tool error"
                else:
                    data = json.loads(raw)
                    print("  Result:")
                    print(f"{json.dumps(data, indent=2, ensure_ascii=False)}\n")

        if failure_message:
            print(f"\nTest failed: {failure_message}", file=sys.stderr)
            sys.exit(1)

        print("All streamable-http tests passed successfully!")
    except Exception as exc:
        print(f"\nTest failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
