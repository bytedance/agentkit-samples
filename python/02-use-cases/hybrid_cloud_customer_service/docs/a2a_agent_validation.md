# A2A 数据分析 Agent：部署、注册与验证

本章验证的是**真实的跨 Runtime A2A 调用**，不是 `demo_core.py` 中的本地 fallback 事件。

角色分工：

| Runtime | 镜像入口 | 职责 |
| --- | --- | --- |
| 企业智能客服 | `AGENT_APP_MODE=customer_service` | 识别投诉趋势需求、发现 Agent Card、委派任务并整合结果 |
| 投诉数据分析 Agent | `AGENT_APP_MODE=a2a_data_analyst` | 提供 Agent Card，执行 A2A `message/send`，返回趋势 Artifact |

两者可以复用同一镜像，但必须是两个独立的 AgentKit Runtime。这样 A2A 中心能独立登记、授权和审计数据 Agent。

## 1. 发布数据分析 A2A Agent

从本 Demo 根目录执行：

```bash
./scripts/deploy_a2a_interactive.sh
```

该入口为数据 Agent 生成独立的本地配置 `agentkit.a2a.yaml`（Git 忽略），复用项目源码构建
`linux/amd64` 镜像，默认命名为 `hybrid-cloud-customer-service-a2a`，自动注入
`AGENT_APP_MODE=a2a_data_analyst`、`PORT=8000`，并等待
Runtime 就绪。主客服 Runtime 仍保持自己的独立 Name/ID 配置。部署脚本会交互收集该数据 Runtime
自己的 Model Name、API Base
和隐藏 API Key，并将其注入 live Runtime；当前固定数据集用于让协议验收结果稳定，不代表 A2A
Agent 不能扩展为模型分析。脚本会在同名 Runtime 已存在时询问更新或创建新名称，不会
静默覆盖。

当前 AgentKit CLI 不提供 A2A 中心的空间创建或 AgentCard 注册命令。发布后，在
**A2A 中心 → 注册 A2A 智能体 → 智能体运行时** 中选择这个 Runtime，完成首次空间/授权确认。
平台已知该 Runtime 的服务地址，会按该地址发现和登记 AgentCard；因此在 AgentKit Runtime
注册模式下，**不需要填写 `A2A_PUBLIC_URL`，也不需要为此二次发布**。

数据 Agent 对外暴露：

```text
GET  <A2A_PUBLIC_URL>/.well-known/agent-card.json
POST <A2A_PUBLIC_URL>/a2a
```

代码入口在 [a2a_data_agent.py](../a2a_data_agent.py)。它使用 `a2a-sdk` 的
`A2AStarletteApplication` 和 `DefaultRequestHandler`，在 AgentCard 的
`skills[].id` 中声明 `complaint-trend-analysis` 能力；任务返回标准 A2A Task、Artifact
和完成状态。这里的 `skills` 是 A2A 协议字段，不是 AgentKit Skills 中心。

## 2. 获取数据 Runtime 调用信息并直接验收

在数据 Runtime 的 **快速调用/在线测试/调用信息** 页复制它自己的 Endpoint 和 API Key。
在 A2A 中心登记完成后，再复制登记详情中的“服务地址”；它是主 Runtime 的对端地址来源。
Endpoint/API Key 仅在本地当前终端临时使用，不能使用主客服 Runtime 的 Key 替代。

```bash
export A2A_AGENT_BASE='https://<data-agent-runtime-public-base>'
export A2A_AGENT_API_KEY='<data-agent-runtime-api-key>'
```

验证 Card：

```bash
curl -sS "$A2A_AGENT_BASE/.well-known/agent-card.json" \
  -H "Authorization: Bearer $A2A_AGENT_API_KEY"
```

预期 JSON 包含：

```json
{
  "name": "hybrid-cloud-complaint-data-agent",
  "url": "https://<data-agent-runtime-public-base>/a2a",
  "skills": [{"id": "complaint-trend-analysis"}]
}
```

再验证标准 A2A 请求：

```bash
curl -sS -X POST "$A2A_AGENT_BASE/a2a" \
  -H "Authorization: Bearer $A2A_AGENT_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "a2a-proof-001",
    "method": "message/send",
    "params": {
      "message": {
        "kind": "message",
        "messageId": "m-a2a-proof-001",
        "role": "user",
        "parts": [{"kind": "text", "text": "分析过去一年的投诉趋势并预测下季度"}]
      },
      "configuration": {"blocking": true}
    }
  }'
```

预期 HTTP 200，`result.artifacts[0].name` 为 `complaint-trend-analysis`，文本包含“已由 A2A 数据分析 Agent 完成”。若是 401，检查该请求是否使用了数据 Agent Runtime 自己的 API Key。

## 3. 注册到 A2A 中心

进入 **AgentKit → A2A 中心 → 注册 A2A 智能体**：

1. 选择目标 A2A 智能体空间（没有则按平台提示创建）。
2. 选择通过智能体运行时注册，或输入上一步验证成功的 Agent Card URL。
3. 选择控制台自动带出的“服务地址”，保存注册。
4. 注册完成后确认平台生成的 Card 预览中展示 Agent 名称、所需 AgentCard 能力 ID、版本和服务地址。

注册是平台治理和发现入口；一个 A2A 中心/空间可包含多个 Agent，平台会根据人工选中的
AgentCard 和 Runtime 服务地址定位对端。本 Demo 默认 Agent/AgentCard 能力为
`hybrid-cloud-complaint-data-agent` / `complaint-trend-analysis`，它们是业务验收默认值而非
A2A 中心的固定全局配置。不要把 Skills 中心的 Skill、Skills Space ID (`ss-...`) 或
Sandbox Tool ID (`t-...`) 填到 A2A 配置中。

## 4. 将已登记对端安全配置到客服主 Runtime

不要在控制台手工替换完整环境变量列表，也不要使用 `--envs-json`。从本 Demo 根目录执行：

```bash
./scripts/configure_a2a_peer_interactive.sh
```

脚本会：

1. 从本地 `agentkit.yaml` 读取主客服 Runtime ID，并要求你确认目标；
2. 要求输入主 Runtime Region 和从 A2A 中心详情复制的服务地址；服务地址末尾未带 `/a2a`
   时自动补齐；
3. 隐藏输入数据 Runtime 自己的 API Key，读取 AgentCard 并自动取得名称和
   `skills[].id`；若 Card 有多个能力，仅要求从已发现的列表中选择；
4. 只合并更新 `A2A_DATA_AGENT_URL`、`A2A_DATA_AGENT_API_KEY`、
   `A2A_DATA_AGENT_NAME`、`A2A_DATA_AGENT_SKILL_ID`、
   `A2A_DATA_AGENT_TIMEOUT_SECONDS=30`，不覆盖模型 Key、Knowledge、Memory、Session 或 Tool 配置；
5. 自动 release 主 Runtime 并等待 `Ready`。

`A2A_DATA_AGENT_API_KEY` 仅保留在主 Runtime 环境，不进入浏览器、本地 UI LocalStorage、
响应、日志或仓库。Card URL 默认由 `/a2a` 自动推导，通常无需单独填写。

主 Agent 在 [agent.py](../agent.py) 的构造阶段仅在 `A2A_DATA_AGENT_URL` 存在时注册 `delegate_complaint_trend_analysis`。函数实现在 [a2a_client.py](../a2a_client.py)：

```python
async with httpx.AsyncClient(
    timeout=config.timeout_seconds,
    follow_redirects=True,
) as client:
    card = await _discover(client, config)
    response = await client.post(
        config.rpc_url,
        headers={**_headers(config), "Content-Type": "application/json"},
        json={
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": message,
                "configuration": {"blocking": True},
            },
        },
    )
    response.raise_for_status()
```

因此链路是“**Card 发现 → AgentCard 能力校验 → `/a2a` 委派 → Artifact 回传**”，
而不是主 Agent 在本地直接调用 `complaint_trend()`，也不是调用 Skills Sandbox。
这里必须使用异步 HTTP 客户端；同步请求会阻塞 ADK 调用，可能导致 FaaS 取消请求并产生
`Missing tool results`。
`delegate_complaint_trend_analysis` 是本 Demo 的投诉分析业务适配器，不代表 A2A 中心只能有这一个
Agent。运行时实际校验的是人工选中并写入 `A2A_DATA_AGENT_NAME` /
`A2A_DATA_AGENT_SKILL_ID` 的 Card；接入另一类业务 Agent 时应新增相应的窄业务工具，而不是让模型
任意选择 URL。

## 5. 最终验收：确认码、双端调用与 Trace

从本 Demo 根目录执行：

```bash
./scripts/verify_a2a_interactive.sh --show-response
```

脚本会隐藏输入主客服与数据 Runtime 的 Endpoint/API Key，并生成一次性
`A2A_CANARY_<随机值>`。它按同一确认码依次验证：

1. 数据 Runtime 的 AgentCard 名称与能力 ID (`skills[].id`) 等于本次从 A2A 中心选择的值；
2. `/health` 只读确认 Model Name/API Base/API Key 三项存在，不显示任何值；
3. 直接 `POST /a2a` 返回 Artifact、远端完成说明和确认码；
4. 主客服 Runtime 通过 `delegate_complaint_trend_analysis` 委派后，最终可见回答返回远端 Agent
   名称 `hybrid-cloud-complaint-data-agent`、远端完成说明和**同一个**确认码。展示标题可随模型措辞变化，
   不要求固定中文句式。

脚本输出主 Runtime 的 `user_id`、`session_id` 和确认码。Trace 判定方法：

1. 打开主 Runtime 的可观测 → Trace，按脚本输出的 `user_id` 或 `session_id` 过滤；打开该条
   Trace，在 Tool Span 中确认 `execute_tool delegate_complaint_trend_analysis`，并确认输出包含确认码。
2. 打开数据 Runtime 的日志或 Trace，搜索同一确认码；必须看到
   `GET /.well-known/agent-card.json 200` 与 `POST /a2a 200`。
3. 将“脚本三项 PASS + 主 Runtime Tool Span + 数据 Runtime 两个 HTTP 200”作为端到端通过证据。

主 Runtime 没有额外打印 A2A INFO 日志不代表失败；同一码的双端 HTTP/Tool 证据才是判定依据。

## 常见失败

| 现象 | 原因与处理 |
| --- | --- |
| Card 访问 404 | 检查数据 Agent 是否以 `AGENT_APP_MODE=a2a_data_analyst` 运行；从 A2A 中心选中的服务地址发起请求，且 URL 没有错误拼接 `/invoke`。 |
| Card 访问 401 | API Key 是数据 Agent Runtime 的 Key；配置到主 Runtime 的 `A2A_DATA_AGENT_API_KEY` 也必须是它。 |
| 主 Agent 不调用委派工具 | 主 Runtime 缺少 `A2A_DATA_AGENT_URL` 或没有重新发布；使用明确包含函数名的验收提示。 |
| `A2A Agent Card does not advertise required skill` | 这是 A2A SDK 的协议错误措辞；表示注册/部署的不是本样例数据 Agent，或 AgentCard 的 `skills[].id` 中缺少 `complaint-trend-analysis`，与 Skills 中心无关。 |
| A2A 中心可见但主 Agent 调用失败 | 平台登记不等于运行时网络连通；先按第 2 步直接 curl 对端。 |
| 只有主 Runtime Tool Span | 说明模型选择了委派工具，但尚不足以证明对端成功；运行确认码脚本并补齐数据 Runtime 的 AgentCard `GET 200`、`POST /a2a 200`。 |
