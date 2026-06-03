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

import asyncio
import json
import os
import sys
from mcp_client import RedisMCPClient


def detect_credential_mode():
    if os.getenv("AUTHORIZATION") or os.getenv("authorization"):
        return "Authorization STS"
    if os.getenv("VOLCENGINE_SESSION_TOKEN"):
        return "AK/SK + SessionToken"
    return "AK/SK"


def pretty_print_json(raw_text: str) -> str:
    try:
        return json.dumps(json.loads(raw_text), indent=2, ensure_ascii=False)
    except Exception:
        return raw_text


async def test_server():
    region = os.getenv("VOLCENGINE_REGION") or "cn-beijing"

    print("Testing Volcengine Redis MCP Server...")
    print(f"Resolved region for requests: {region}")
    print(f"Detected credential mode: {detect_credential_mode()}")

    try:
        async with RedisMCPClient() as client:
            print("\n1. Successfully connected to MCP server.")

            # --- 1. List available tools ---
            tools = await client.list_tools()
            print(f"\n2. Retrieved {len(tools)} tools:")
            for i, tool in enumerate(tools[:5]):  # show first 5
                print(f"  - {tool['name']}: {tool['description'][:60]}...")
            if len(tools) > 5:
                print(f"  ... and {len(tools) - 5} more tools.")

            # --- 2. Test a parameterless read-only tool ---
            print("\n3. Testing tool invocation: describe_regions")
            regions_result = await client.call_tool("describe_regions", {})
            print("  Result:")
            print(f"{pretty_print_json(regions_result)}\n")

            # --- 3. Test an advanced tool with arguments ---
            print("4. Testing tool invocation: describe_db_instances (with args)")
            # Requesting only 1 instance to keep the output concise
            instances_result = await client.call_tool(
                "describe_db_instances", {"region_id": region, "page_size": 1}
            )
            print("  Result:")
            data = json.loads(instances_result)
            if "instances" in data and len(data["instances"]) > 0:
                data["instances"] = data["instances"][:1]
                data["_note"] = (
                    "Output truncated to 1 instance by test script for brevity"
                )
            print(f"{json.dumps(data, indent=2, ensure_ascii=False)}\n")

            print("\nAll tests passed successfully!")

    except Exception as e:
        print(f"\nTest failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_server())
