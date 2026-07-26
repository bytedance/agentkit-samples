# 步骤 07：A2A 与身份权限

## A2A

主客服 Runtime 与投诉数据分析 Runtime 是两个独立目标。数据 Agent 可自动部署：

```bash
./scripts/deploy_a2a_interactive.sh
```

脚本会复用本次终端/CLI 已确认的目标环境，明确询问 Region，创建或更新独立的
`hybrid-cloud-customer-service-a2a` Runtime，并自动注入
`AGENT_APP_MODE=a2a_data_analyst`、`PORT=8000`、交互输入的 Agent 名称/Skill ID，并按主 Runtime
相同方式收集 Model Name、API Base 和隐藏 API Key。它不会改写主客服 Runtime 的本地 Name/ID 绑定。和首个 Runtime 一样，
若 Registry 临时登录已过期，按脚本提示在本机刷新登录后重试。

当前 CLI 未提供 A2A 中心的注册接口，因此首次治理动作需要人工确认：在 A2A 中心选择
数据 Runtime、选择/创建 A2A 空间并登记 AgentCard。登记完成后按以下顺序继续：

1. 在数据 Runtime 的“快速调用/调用信息”页复制该 Runtime 的 API Key；不要使用主客服
   Runtime 的 Key，也不要粘贴到对话、`.env` 或仓库。
2. 在 A2A 中心已登记 Agent 的详情页复制 Agent 名称、要使用的 Skill ID 和“服务地址”。A2A
   中心可登记多个 Agent；不要把本 Demo 默认的投诉分析 Agent 当成中心唯一对象。
3. 在本地终端执行：

   ```bash
   ./scripts/configure_a2a_peer_interactive.sh
   ```

   脚本显示并要求确认主客服 Runtime ID，要求明确输入其 Region、A2A Agent 名称、Skill ID、
   服务地址，并隐藏输入
   数据 Runtime API Key。它只合并写入 `A2A_DATA_AGENT_URL`、
   `A2A_DATA_AGENT_API_KEY`、`A2A_DATA_AGENT_NAME`、`A2A_DATA_AGENT_SKILL_ID`、
   `A2A_DATA_AGENT_TIMEOUT_SECONDS`，保留已有模型与
   组件环境变量，然后自动 release 并等待 `Ready`。
4. 从主客服 Runtime 的“快速调用/调用信息”页取得主 Runtime 的 Endpoint/API Key，使用
   [A2A 验收文档](../a2a_agent_validation.md) 的最终委派请求或本地 `/chat` 新建会话验证。

配置完成后验证：

1. AgentCard 发现；
2. 数据 Runtime 的 Model Name/API Base/API Key 三项已注入（只返回布尔值，不显示内容）；
3. 人工选中的 Skill ID 校验；
4. 标准 `message/send` 委派；
5. Artifact 回传与 A2A Trace。

使用以下脚本做一次性确认码验收；它会隐藏输入主/数据 Runtime 的 Endpoint 与 API Key：

```bash
./scripts/verify_a2a_interactive.sh --show-response
```

通过时记录输出的 `A2A_CANARY_<随机值>`、主 Runtime `user_id` 和 `session_id`。在平台可观测
中按该 user/session 定位主 Runtime Trace，必须看到 `execute_tool delegate_complaint_trend_analysis`；
再到数据 Runtime 日志/Trace 按同一确认码检索，必须同时看到 AgentCard 的 `GET 200` 和
`POST /a2a 200`。三类证据缺少任一项均只能判为部分通过。

详细配置见[A2A 数据分析 Agent 验证](../a2a_agent_validation.md)。

## 身份

- 生产签名验证必须由 AgentKit 网关和用户池/JWT 策略完成；
- Runtime 只消费已验签 claims；
- token 与 Body 中 tenant/user 不一致必须拒绝；
- OAuth、用户池和生产权限修改需要人工授权。

PostgreSQL 会话资源、跨会话记忆和用户隔离已在步骤 02–04 完成，不在本步骤重复验收。
A2A 与身份分别判定，不能用 demo fallback 代替真实平台通过。
