# AgentKit MCP 服务接入与验收

本模块使用官方 `@modelcontextprotocol/server-sequential-thinking` 作为连通性示例。它不需要第三方账号和业务数据，只暴露 `sequential_thinking`，适合验证 MCP 工具发现和调用。生产环境应替换为经过治理的业务 MCP。

> 未采用 Python `mcp-server-time`：平台通过 `uvx` 冷启动时需要下载 `pydantic-core`、`cryptography` 等依赖，实测 120 秒内未监听 8000，触发 FaaS 启动超时。Node 参考服务依赖更轻，也更符合平台默认示例。

## 1. 在 AgentKit 部署 MCP 服务

进入 **网关 → MCP 服务 → 创建 MCP 服务 → 部署 MCP 服务**，填写：

- 协议：`Streamable HTTP`
- 访问路径：`/mcp`
- 网络：公网访问（便于当前 Runtime 验收）
- 入站认证：`API Key`
- 后端配置：`JSON 配置`

```json
{
  "mcpServers": {
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

创建并发布后，确认服务状态为“运行中”。此时只完成了协议服务托管，尚未把它暴露给主 Runtime。

## 2. 创建 MCP 工具集

进入 **网关 → MCP 工具集 → 创建 MCP 工具集**：

- 名称：例如 `hybrid-customer-service-mcp-tools`
- MCP 服务：选择上一步的 `mcp_service_demo2`
- 工具范围：当前单服务验收可选“全部工具”；若逐项选择，只加入 `sequential_thinking`
- 路径：`/mcp`
- 路由模式：单工具可直接使用全部工具模式；工具较多时再使用语义检索或标签检索
- 认证：由工具集生成并管理，不复用主 Runtime API Key

工具集状态就绪后，可先用工具集页面的“调用示例”确认它能列出并调用 `sequential_thinking`。

在创建工具集前，先进入目标 MCP 服务的 **调试** 页：

1. 选择服务域名；
2. 在页面内输入该服务的 API Key（不要复制到聊天、文档或终端历史）；
3. 点击 **连接测试**；
4. 连接完成后，确认第二栏能列出工具，再测试目标工具。

若连接测试持续转圈或超时，首个失败点是 MCP 服务传输/启动，不是工具范围。此时服务
或工具集显示 `Ready` 也不能证明后端进程已经监听并完成工具发现。先查看脱敏服务日志，
依次排查：

- 进程是否成功启动并监听平台要求的 Streamable HTTP 入口；
- 依赖是否在冷启动阶段下载超时；
- `/mcp` 路径和协议是否匹配；
- DNS、外网访问和认证是否失败。

只有连接测试成功后，空工具列表才可以继续定位为工具未暴露或工具集未勾选。
`GetMCPTools` 返回 `InvalidResource.NotFound` 在连接结果未知时是歧义证据，不能单独证明
目标工具没有被选择。

多服务工具集需要逐个完成连接测试：其中一个服务超时，可能中断或截断整次聚合工具发现，
导致另一个健康服务的工具也不出现在列表中。为获得可重复的验收结果，优先创建只包含
`mcp_service_demo2` 的单服务工具集；若复用多服务工具集，则必须先证明其中每个服务均可连接。

## 3. 关联客服主 Runtime

进入客服主 Runtime 的 **关联组件 → MCP 工具集 → 编辑**，选择上一步的工具集，保存后重新发布 Runtime。平台在发布阶段自动注入：

```text
TOOL_MCP_ROUTER_URL
TOOL_MCP_ROUTER_API_KEY
```

这两个值属于平台注入结果，不需要操作者复制 MCP 服务 URL/Key，更不能写入 Prompt、前端、镜像或 Git。

## 4. Agent 代码如何使用

[`platform_mcp.py`](../platform_mcp.py) 在检测到完整注入后，先兼容混合云当前注入的 Base URL，再延迟导入 VeADK 内置路由器：

```python
def build_platform_mcp_router():
    if not (os.getenv("TOOL_MCP_ROUTER_URL") and
            os.getenv("TOOL_MCP_ROUTER_API_KEY")):
        return None
    url = normalize_mcp_router_url(os.environ["TOOL_MCP_ROUTER_URL"])
    os.environ["TOOL_MCP_ROUTER_URL"] = url
    from veadk.tools.builtin_tools.mcp_router import mcp_router
    return mcp_router
```

当前混合云平台注入的 `TOOL_MCP_ROUTER_URL` 是工具集公网 Base URL，而 VeADK 0.5.40 会原样使用它；实际 Streamable HTTP 入口在 `/mcp`。适配层仅在 URL 尚未以 `/mcp` 结尾时追加该路径，已经是完整地址则不修改。API Key 和完整连接地址不会写入日志。

[`agent.py`](../agent.py) 将 `mcp_router` 加入主 Agent 的 `tools`。VeADK 使用平台注入的工具集入口完成工具发现、路由和 MCP 调用；业务代码不连接单个 MCP 服务，也不自行拼 JSON-RPC。

## 5. 从主 Runtime 验收

```bash
curl -sN -X POST "${RUNTIME_ENDPOINT%/}/invoke" \
  -H "Authorization: Bearer $RUNTIME_API_KEY" \
  -H "Content-Type: application/json" \
  -H "user_id: mcp-verify-user" \
  -H "session_id: mcp-verify-001" \
  -d '{"prompt":"必须调用 MCP 的 sequential_thinking 工具，分步骤分析：客户申请理财产品退款时，客服应先核验哪些信息？不要改用 run_code；返回工具名和最终结论。"}'
```

验收必须同时满足：

1. 主 Runtime 返回成功，答案说明调用了 `sequential_thinking` 并给出分析结论；
2. MCP 工具集/服务日志或 Trace 出现工具发现与 `tools/call`；
3. 临时解除 Runtime 与工具集的关联并发布后，同一请求不再产生 MCP 调用，证明不是本地伪造结果。

主 Runtime 启动日志还应出现：

```text
AgentKit MCP router base URL detected; appended Streamable HTTP path /mcp.
AgentKit MCP toolset router enabled from Runtime association.
```

第一行只在平台注入 Base URL 时出现；若未来平台直接注入完整 `/mcp` 地址，则只出现第二行。

在发布 Runtime 前，也可以用工具集的公网 Base URL直接验证协议入口（不要把 Key 粘贴到聊天或文档）：

```bash
curl -i -N --connect-timeout 10 --max-time 30 \
  -X POST "${TOOL_MCP_ROUTER_URL%/}/mcp" \
  -H "Authorization: Bearer $TOOL_MCP_ROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"agentkit-mcp-check","version":"1.0.0"}}}'
```

返回 `HTTP 200`、`mcp-session-id`，并在事件中看到 `serverInfo`，表示 MCP 工具集的网络、认证和协议均已连通。

若日志显示 `AgentKit MCP disabled`，先检查是否已关联工具集并在关联后重新发布；仅创建 MCP 服务不会注入路由变量。

诊断时按以下顺序记录首个失败层，后续层不得越级判定：

1. 服务连接测试；
2. 服务工具发现；
3. 工具集工具范围；
4. Runtime 关联与关联后发布；
5. Runtime 真实调用与 Tool Span。

## 6. 能力边界

| 能力 | Agent 代码入口 | 平台配置 |
|---|---|---|
| MCP | `mcp_router` | 关联 MCP 工具集后平台注入 `TOOL_MCP_ROUTER_*` |
| AIO Sandbox | `run_code` | `AGENTKIT_TOOL_ID` |
| Skills Sandbox | `execute_skills` | `AGENTKIT_TOOL_ID` + `SKILL_SPACE_ID` |

本地 Demo 的 `/mcp` 仅用于离线协议测试，不是本次平台 MCP 验收链路。
