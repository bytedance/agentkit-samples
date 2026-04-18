#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
import sys
from mcp_client import RedisMCPClient

async def test_server():
    print("Testing Volcengine Redis MCP Server...")
    
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
                
            # --- 2. Test a basic tool (no arguments required) ---
            print("\n3. Testing tool invocation: describe_regions")
            regions_result = await client.call_tool("describe_regions", {})
            print("  Result:")
            print(f"{regions_result}\n")
            
            # --- 3. Test an advanced tool with arguments ---
            print("4. Testing tool invocation: describe_db_instances (with args)")
            # Requesting only 1 instance to keep the output concise
            instances_result = await client.call_tool("describe_db_instances", {
                "region": "cn-beijing",
                "pageSize": 1
            })
            print("  Result:")
            try:
                import json
                data = json.loads(instances_result)
                if "instances" in data and len(data["instances"]) > 0:
                    data["instances"] = data["instances"][:1]
                    data["_note"] = "Output truncated to 1 instance by test script for brevity"
                print(f"{json.dumps(data, indent=2, ensure_ascii=False)}\n")
            except Exception:
                print(f"{instances_result}\n")
            
            print("\nAll tests passed successfully!")
            
    except Exception as e:
        print(f"\nTest failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_server())
