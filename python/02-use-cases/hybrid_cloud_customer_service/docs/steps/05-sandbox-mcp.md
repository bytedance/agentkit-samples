# 步骤 05：验证 AIO Sandbox 与平台 MCP

## AIO Sandbox

1. 在 **AgentKit → 工具** 创建或复用 AIO Sandbox。
2. 关联到 Runtime，release 并等待 `Ready/Healthy`。
3. 明确要求 Agent 调用 `run_code`：

```text
请使用 run_code 在 Sandbox 中计算 (1284650 / 237)，只返回计算式和结果。
```

预期约为 `5420.464135`。Runtime 日志/Trace 应出现真实 Sandbox endpoint、
session 或调用响应；本地 `python -I` 回退不算平台证据。

## 平台 MCP

1. 在 **网关 → MCP 服务** 创建 Streamable HTTP MCP 服务。
2. 在 **MCP 工具集** 加入服务和需要的工具。
3. 关联工具集到 Runtime，release 并等待就绪。
4. 明确要求调用 `mcp_router`，核对最终回答和 Tool Span。

平台会注入 `TOOL_MCP_ROUTER_URL` 和 `TOOL_MCP_ROUTER_API_KEY`。不要输出这些
变量，也不要把本地 Demo `/mcp` 当作平台 MCP 通过。

详细控制台配置、Sequential Thinking 示例和 curl 验收见
[MCP 服务接入与验收](../mcp_validation.md)。

Sandbox 与 MCP 必须分开判定；任一只有配置截图、没有真实调用证据时标记为部分通过。
