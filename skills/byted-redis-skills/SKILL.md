---
name: volcengine-redis-mcp
description: A skill to launch and interact with the Volcengine Redis MCP Server. This skill enables agents to manage Redis instances, databases, accounts, backups, and configurations using the MCP protocol. It connects to Volcengine via the provided credentials.
---

# Volcengine Redis MCP Server Skill

## 🔵 Overview
This skill provides a complete set of tools to interact with Volcengine Redis using the Model Context Protocol (MCP). It allows users to query instances, manage parameters, and perform operational tasks on Volcengine Redis through natural language or programmatic invocation.

---

## Supported Tools

The MCP Server exposes the following capabilities:
1. `describe_regions` - Query available regional resources.
2. `describe_zones` - Query available zone resources.
3. `describe_vpcs` - Query VPCs.
4. `describe_subnets` - Query subnets.
5. `describe_db_instances` - List Redis instances.
6. `describe_db_instance_detail` - View details for a specific instance.
7. `describe_db_instance_specs` - List supported instance specs.
8. `describe_slow_logs` - Query slow logs.
9. `describe_hot_keys` - Query hot keys.
10. `describe_big_keys` - Query big keys.
11. `describe_backups` - Query backup list.
12. `describe_db_instance_params` - List instance parameters.
13. `describe_parameter_groups` - Query parameter templates.
14. `describe_parameter_group_detail` - View parameter template details.
15. `describe_allow_lists` - Query IP whitelists.
16. `describe_allow_list_detail` - View whitelist details.
17. `list_db_account` - Query database accounts.
18. `create_db_instance` - Create a Redis instance.
19. `modify_db_instance_params` - Modify parameter configurations.
20. `create_db_account` - Create an account for a Redis instance.
21. `create_allow_list` - Create a new IP whitelist.
22. `associate_allow_list` - Bind a whitelist to an instance.
23. `disassociate_allow_list` - Unbind a whitelist from an instance.
24. `describe_db_instance_shards` - Query shard information.
25. `describe_node_ids` - Query node IDs.
26. `modify_db_instance_name` - Modify an instance's name.
27. `describe_tags_by_resource` - Query tags.
28. `describe_backup_plan` - Query backup plan.
29. `describe_pitr_time_window` - Query PITR time window.
30. `describe_backup_point_download_urls` - Get backup point download URLs.
31. `describe_cross_region_backup_policy` - Query cross-region backup policy.
32. `describe_cross_region_backups` - Query cross-region backups.
33. `create_parameter_group` - Create a parameter group.
34. `create_db_endpoint_public_address` - Create a public endpoint.
35. `describe_db_instance_bandwidth_per_shard` - Query shard bandwidth.
36. `describe_db_instance_acl_commands` - Query supported ACL commands.
37. `describe_db_instance_acl_categories` - Query supported ACL categories.
38. `describe_planned_events` - Query planned events.
39. `describe_key_scan_jobs` - Query key scan jobs.
40. `describe_eip_addresses` - Query EIP addresses.

## 🔧 Prerequisites
- Python 3.10+
- `uv` package manager (installed)
- Volcengine account with proper permissions for Redis and VPC services.

## 🔐 Environment Variables
Before running the skill, export the required credentials:
```bash
export VOLCENGINE_ACCESS_KEY="your-access-key"
export VOLCENGINE_SECRET_KEY="your-secret-key"
export VOLCENGINE_REGION="cn-beijing"  # Or your desired region
```

## 🚀 Usage

### 1. Test & Client Example
Use the provided script to verify the server and view usage examples:
```bash
uv run scripts/call_redis_mcp_example.py
```

### 2. Service Management (Optional)
To run the server as a daemon:
```bash
./scripts/start_volcengine_redis_mcp.sh
./scripts/status_volcengine_redis_mcp.sh
./scripts/stop_volcengine_redis_mcp.sh
```

## 💻 Programmatic Usage via MCP Client

You can use the provided Python scripts to programmatically call the MCP Server:

```python
import asyncio
import sys
# Ensure imports work from the scripts directory
sys.path.append("scripts")
from mcp_client import RedisMCPClient

async def main():
    async with RedisMCPClient() as client:
        await client.connect()
        
        # List tools
        tools = await client.list_tools()
        print("Available tools:", [t['name'] for t in tools])
        
        # Call a tool
        result = await client.call_tool("describe_db_instances", {})
        print(result)

asyncio.run(main())
```
