# 步骤 07：A2A 与身份权限

## A2A

主客服 Runtime 与投诉数据分析 Runtime 是两个独立目标。数据 Agent 可自动部署：

```bash
./scripts/deploy_a2a_interactive.sh
```

脚本会复用本次终端/CLI 已确认的目标环境，明确询问 Region，创建或更新独立的
`hybrid-cloud-customer-service-a2a` Runtime，并自动注入
`AGENT_APP_MODE=a2a_data_analyst`、`PORT=8000`、交互输入的 Agent 名称/AgentCard 能力 ID，并按主 Runtime
相同方式收集 Model Name、API Base 和隐藏 API Key。它不会改写主客服 Runtime 的本地 Name/ID 绑定。和首个 Runtime 一样，
若 Registry 临时登录已过期，按脚本提示在本机刷新登录后重试。

### 先区分 A2A 能力与 Skills 中心

| 配置 | 所属能力 | 用途 |
| --- | --- | --- |
| `AgentCard.skills[].id` | A2A 协议 | 声明并选择远端 Agent 提供的业务能力 |
| `A2A_DATA_AGENT_SKILL_ID` | 本 Demo 的兼容环境变量名 | 保存上述 AgentCard 能力 ID |
| `SKILL_SPACE_ID` / `execute_skills` | AgentKit Skills 中心 | 加载已发布 ZIP Skill，并交给 Skills Sandbox 执行 |

A2A 规范本身使用字段名 `skills`，但它与步骤 06 的 Skills 中心不是同一套资源。A2A
配置中不要填写 `ss-...` 的 Skills Space ID、Skills Sandbox Tool ID 或 ZIP 包名称。

当前 CLI 未提供 A2A 中心的注册接口，因此首次治理动作需要人工确认：在 A2A 中心选择
数据 Runtime、选择/创建 A2A 空间并登记 AgentCard。登记完成后按以下顺序继续：

1. 在数据 Runtime 的“快速调用/调用信息”页复制该 Runtime 的 API Key；不要使用主客服
   Runtime 的 Key，也不要粘贴到对话、`.env` 或仓库。
2. 在 A2A 中心已登记 Agent 的详情页复制“服务地址”。详情页不一定直接显示能力 ID；
   右上角“JSON 文件”中的 `skills[].id` 是其来源，但正常流程无需人工下载或抄写，后续脚本会
   自动读取。A2A 中心可登记多个 Agent；不要把本 Demo 默认的投诉分析 Agent 当成中心唯一对象。
3. 在本地终端执行：

   ```bash
   ./scripts/configure_a2a_peer_interactive.sh
   ```

   脚本显示并要求确认主客服 Runtime ID，要求明确输入其 Region 和服务地址，并隐藏输入
   数据 Runtime API Key。随后读取 `/.well-known/agent-card.json`，自动取得 Agent 名称和
   `skills[].id`；单能力自动选择，多能力时列出后让用户选择。它只合并写入 `A2A_DATA_AGENT_URL`、
   `A2A_DATA_AGENT_API_KEY`、`A2A_DATA_AGENT_NAME`、`A2A_DATA_AGENT_SKILL_ID`、
   `A2A_DATA_AGENT_TIMEOUT_SECONDS`，保留已有模型与
   组件环境变量，然后自动 release 并等待 `Ready`。
4. 从主客服 Runtime 的“快速调用/调用信息”页取得主 Runtime 的 Endpoint/API Key，使用
   [A2A 验收文档](../a2a_agent_validation.md) 的最终委派请求或本地 `/chat` 新建会话验证。

配置完成后验证：

1. AgentCard 发现；
2. 数据 Runtime 的 Model Name/API Base/API Key 三项已注入（只返回布尔值，不显示内容）；
3. 人工选中的 AgentCard 能力 ID 校验；
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

身份验收不能把主客服 Runtime 从 API Key 原地改成 OAuth JWT。为避免影响已经验证过的
Knowledge、Memory、Sandbox、MCP、Skills 和 A2A，必须创建独立兄弟 Runtime：

```text
主 Runtime：hybrid-cloud-customer-service        API Key，保持不变
身份 Runtime：hybrid-cloud-customer-service-oauth OAuth JWT，仅做身份验收
```

### 1. 准备用户池 Client

在控制台打开目标 Runtime 可访问的用户池，确认或创建一个仅用于 Demo 的
`client_credentials` Client，记录非敏感的用户池 ID 和 Client ID。Client Secret 只在本地
交互输入，不能粘贴到对话、README、`.env`、截图或 Git。

控制面上的 `GetUserPool`、`ListUserPoolClients`、`GetUserPoolClient` 只用于确认资源；
真正的 Access Token 来自用户池认证域名：

```text
http://auth.<环境域名>/userpool/<用户池ID>/oauth/token?grant_type=client_credentials
```

### 2. 部署独立 OAuth Runtime

```bash
./scripts/deploy_oauth_interactive.sh
```

按提示输入认证域名协议/域名、用户池 ID 和允许访问的 Client ID。脚本先验证 OIDC
Discovery，再把以下非敏感配置写入独立的 `agentkit.oauth.yaml`：

```yaml
launch_types:
  hybrid:
    runtime_name: hybrid-cloud-customer-service-oauth
    runtime_auth_type: custom_jwt
    runtime_jwt_discovery_url: <用户池 OIDC Discovery URL>
    runtime_jwt_allowed_clients:
      - <Client ID>
```

随后脚本复用标准交互部署流程收集 Region、控制面和模型配置。它不会读取 Client Secret，
也不会修改主 Runtime 的 `agentkit.yaml` 或平台组件关联。首次发布后，在 OAuth Runtime
详情页确认“可访问用户池”正确、状态为 `Ready / RUNNING / Healthy`。

当前混合云 POC 的用户池认证域名可能只有 HTTP，而 AgentKit CLI 0.5.5 的本地配置校验
默认只接受 HTTPS。用户明确选择 HTTP 时，脚本会仅在本次子进程中放宽该项本地校验；
不会修改已安装 SDK，也不会影响主 Runtime。正式环境必须选择 HTTPS。若旧版脚本在
`Checking configured .../ping` 后直接退出且平台没有出现 OAuth Runtime，这是部署前
校验失败，并不代表 Runtime 创建失败；更新脚本后重试即可。

### 3. 获取短期 Token 并调用 Runtime

```bash
./scripts/verify_oauth_interactive.sh --show-response
```

脚本交互输入 OAuth Runtime Endpoint、用户池 ID 和 Client ID；仅 Client Secret 隐藏输入。
随后通过 Discovery 取得 Token Endpoint，以 HTTP Basic Client 认证换取短期 Access Token，
再执行唯一的默认验收链路：

1. 从用户池取得短期 `access_token`；
2. 使用 `Authorization: Bearer <access_token>` 调用独立 OAuth Runtime 的 `/invoke`；
3. 要求 HTTP 200，并能解析出最终回答。

这不是一套独立的 OAuth 服务验收；Token 获取只是调用 Runtime 的前置动作。默认通过时看到
`OAuth token` 和 `OAuth Runtime invoke` 两条 PASS 即可。脚本不打印、不写入 Access Token
或 Client Secret。

只有需要额外演示网关拒绝行为时才运行：

```bash
./scripts/verify_oauth_interactive.sh --show-response --negative-checks
```

此时再要求缺失和伪造 Bearer 均返回 HTTP 401/403；它们不是默认正向链路的前置条件。

### 4. Trace 与能力边界

首个 OAuth 请求必须是无工具 Prompt，避免把入站用户 JWT 误当成 Knowledge、MCP 或 A2A
的下游服务凭据。平台 Trace 中确认 OAuth Runtime 的成功 `/invoke` 和 Agent/Workflow/LLM
Span；不得出现 Authorization/JWT 原文。401/403 在网关阶段被拒绝，可能没有完整 LLM Span。

`client_credentials` 证明的是“应用身份可以通过网关”，不是最终用户登录。若要演示真人用户
身份，应另行配置 Authorization Code + PKCE。网关接受 JWT 也不等于业务 Claim 已映射：
应用层若要按租户隔离，必须从已验签 Claim 读取 `sub`，并由用户池显式提供自定义
`tenant_id`；不得回退相信 Body/Header 中同名字段。

PostgreSQL 会话资源、跨会话记忆和用户隔离已在步骤 02–04 完成，不在本步骤重复验收。
A2A 与身份分别判定，不能用 demo fallback 代替真实平台通过。
