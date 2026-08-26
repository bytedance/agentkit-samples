# User Pool + Skills Sandbox MCP experiment

这个 sample 是一个完整的实验 agent：用户通过 VeIdentity User Pool 登录后，可以在本地
直接调用 agent，也可以把 agent launch 到 AgentKit Runtime 后用本地前端调用云端
Runtime。无论本地还是云端，agent 的核心动作都是通过 `execute_skills` 调用一个线上
Skills Sandbox；Sandbox 内部已经配置好 MCP tool。

本 sample 暂不实现 MCP Gateway 侧逻辑。MCP endpoint、MCP tool 配置、下游鉴权和
TIP token 消费都属于 Skills Sandbox 运行环境；这个 Runtime agent 只负责把登录用户
的 inbound token 传给 `execute_skills`。

## 链路

本地 agent 路线：

```text
浏览器用户
-> User Pool OAuth2 登录
-> 本地 app.py / VeADK Web UI
-> 本地 agent
-> ADK credential_service["inbound_auth"]
-> execute_skills
-> 线上 Skills Sandbox
-> Sandbox 内 MCP tool
```

可选云端 agent 路线：

```text
浏览器用户
-> 本地 cloud_client_app.py 登录
-> 本地前端携带 Authorization: Bearer <user token>
-> 已 launch 的 AgentKit Runtime /run_sse
-> 云端 agent
-> execute_skills
-> 线上 Skills Sandbox
-> Sandbox 内 MCP tool
```

额外实验工具：

```text
oauth2_testapp.py
-> 获取 User Pool access token

exchange_user_token_for_tip.py
-> 使用 User Pool access token 换 X-Ve-TIP-Token
```

## 目录说明

```text
.
├── assistant/
│   └── agent.py                    # experiment agent，调用 execute_skills
├── app.py                          # 本地登录 + 本地 VeADK Web UI
├── cloud_client_app.py             # 专用本地登录前端，登录后调用云端 AgentKit Runtime
├── oauth2_testapp.py               # 最小 User Pool access token 获取工具
├── exchange_user_token_for_tip.py  # user token 换 TIP token 工具
├── main.py                         # 可选 AgentKit WebServer App 云端入口
├── agentkit.yaml                   # 可选云端 launch/deploy 模板
├── .env.example                    # 本地和云端变量模板
└── tests/
```

## 配置

```bash
cp .env.example .env
```

常用变量：

| 变量 | 用途 |
| --- | --- |
| `MODEL_AGENT_PROVIDER` / `MODEL_AGENT_NAME` / `MODEL_AGENT_API_BASE` / `MODEL_AGENT_API_KEY` | 本地模型配置 |
| `USERPOOL_ID` / `USERPOOL_CLIENT_ID` / `USERPOOL_DISCOVERY_URL` | 可选云端 Runtime JWT 和前端 OAuth2 配置 |
| `OAUTH2_ISSUER_URI` / `OAUTH2_CLIENT_ID` / `OAUTH2_CLIENT_SECRET` | 本地 OAuth2 登录配置 |
| `OAUTH2_REDIRECT_URI` | `app.py` 登录回调，默认 `http://127.0.0.1:8000/oauth2/callback` |
| `OAUTH2_TESTAPP_REDIRECT_URI` | `oauth2_testapp.py` 回调，默认 `http://127.0.0.1:8082/callback` |
| `CLOUD_CLIENT_REDIRECT_URI` | `cloud_client_app.py` 回调，默认 `http://127.0.0.1:8083/oauth2/callback` |
| `AGENT_RUNTIME_URL` | 已 launch 的云端 Runtime base URL |
| `CLOUD_AGENT_CALL_PATH` | 本地 cloud client 调云端 Runtime 的入口，默认 `invoke`，也可设为 `run_sse` 或 `run` |
| `AGENTKIT_TOOL_ID` / `AGENTKIT_TOOL_ID_SKILLS` | 线上 Skills Sandbox ToolId |
| `SKILL_SPACE_ID` | Skills Sandbox 使用的技能空间 |
| `VE_IDENTITY_WORKLOAD_NAME` | `exchange_user_token_for_tip.py` 使用的 workload identity name |
| `SKILL_SANDBOX_MCP_PROMPT` | 可选，覆盖委托给 Skills Sandbox 的英文任务模板 |

不要把真实 token、client secret、API key、Runtime API key 或网关 header 写入代码、
README、`agentkit.yaml` 或提交记录。

## 安装

依赖使用已包含 Skills Sandbox inbound token / TIP token 透传链路的 VeADK release 版本：

```text
veadk-python==1.1.5
```

```bash
cd python/advanced/userpool-sandbox-mcp-authz
export UV_CACHE_DIR=/private/tmp/uv-cache
uv venv
uv pip install -r requirements.txt
uv run python tests/test_mcp_authz_sample_contract.py
```

## 路线 A：本地登录后直接调本地 agent

```bash
uv run python app.py
```

打开：

```text
http://127.0.0.1:8000
```

完成登录后，在 Web UI 中选择 `assistant`，输入要通过 Skills Sandbox 内 MCP tool
执行的请求。

本地 UI 会：

- 校验 User Pool 登录态。
- 使用 `get_fast_api_app` 承载本地 ADK API，并挂载 VeADK Web UI。
- VeADK OAuth2 中间件会把登录 session 中的 access token 注入为本次请求的
  `Authorization: Bearer <user token>`。
- 本地 `UserTokenStateASGIMiddleware` 会在 `/run` 和 `/run_sse` 的请求体里写入
  一个仅用于本地实验的临时 state key。
- agent tool 调用 `execute_skills` 前，把这个本地 state token 写入 ADK credential
  service 中的 `inbound_auth`。
- VeADK 1.1.5 的 `execute_skills` 再把 `inbound_auth` 传给线上 Skills Sandbox。

## 路线 B：launch 云端 agent 后用本地前端调用

先在 `.env` 里填好云端 launch 所需变量：

```dotenv
USERPOOL_ID=<your_userpool_id>
USERPOOL_CLIENT_ID=<your_userpool_client_id>
USERPOOL_DISCOVERY_URL=https://userpool-<your_userpool_id>.userpool.auth.id.cn-beijing.volces.com/.well-known/openid-configuration
USERPOOL_M2M_CLIENT_ID=

AGENTKIT_TOOL_ID=<your_skills_sandbox_tool_id>
AGENTKIT_TOOL_ID_SKILLS=<your_skills_sandbox_tool_id>
SKILL_SPACE_ID=<your_skill_space_id>
```

然后加载 `.env`，用 `agentkit config` 写入/更新本地 `agentkit.yaml`，再用
`agentkit launch` 构建并部署。`agentkit` 当前不会自动读取 `.env`，所以先把文件里的变量导出到当前 shell：

```bash
set -a
. ./.env
set +a

uv run agentkit config \
  --agent_name userpool-sandbox-mcp-authz \
  --entry_point main.py \
  --language Python \
  --language_version 3.12 \
  --dependencies_file requirements.txt \
  --launch_type cloud \
  --cloud_provider volcengine \
  --region cn-beijing \
  --runtime_name userpool-sandbox-mcp-authz \
  --runtime_auth_type custom_jwt \
  --runtime_jwt_discovery_url "$USERPOOL_DISCOVERY_URL" \
  --runtime_jwt_allowed_clients "$USERPOOL_CLIENT_ID" \
  --tool_id "$AGENTKIT_TOOL_ID" \
  -e "USERPOOL_ID=$USERPOOL_ID" \
  -e "USERPOOL_CLIENT_ID=$USERPOOL_CLIENT_ID" \
  -e "USERPOOL_M2M_CLIENT_ID=$USERPOOL_M2M_CLIENT_ID" \
  -e "AGENTKIT_TOOL_ID=$AGENTKIT_TOOL_ID" \
  -e "AGENTKIT_TOOL_ID_SKILLS=$AGENTKIT_TOOL_ID_SKILLS" \
  -e "SKILL_SPACE_ID=$SKILL_SPACE_ID" \
  -e "SKILL_SANDBOX_MCP_PROMPT=$SKILL_SANDBOX_MCP_PROMPT" \
  -e "OTEL_METRICS_EXPORTER=none" \
  -e "OTEL_TRACES_EXPORTER=none"

uv run agentkit launch --config-file agentkit.yaml
uv run agentkit status --config-file agentkit.yaml --verbose
```

如果你需要同时允许 M2M client 调 Runtime，在 `agentkit config` 命令里额外加一行：

```bash
  --runtime_jwt_allowed_clients "$USERPOOL_M2M_CLIENT_ID" \
```

然后把 Runtime base URL 和本地 cloud client 登录参数写入 `.env`：

```dotenv
AGENT_RUNTIME_URL=https://<your-runtime-endpoint>
CLOUD_CLIENT_REDIRECT_URI=http://127.0.0.1:8083/oauth2/callback
OAUTH2_ISSUER_URI=https://userpool-<your_userpool_id>.userpool.auth.id.cn-beijing.volces.com
OAUTH2_CLIENT_ID=<your_userpool_client_id>
OAUTH2_CLIENT_SECRET=<your_userpool_client_secret>
OAUTH2_SCOPES="openid profile email"
CLOUD_AGENT_CALL_PATH=invoke
```

启动本地 cloud client：

```bash
uv run python cloud_client_app.py
```

打开：

```text
http://127.0.0.1:8083
```

页面是一个专用的轻量云端调用客户端，不再复用完整 VeADK Web UI / Studio 接口。它会：

- 使用本地 OAuth2 session 完成 User Pool 登录。
- 调用本地 `/api/run-cloud`。
- 后端把 `Authorization: Bearer <user token>`、`user_id` 和 `session_id` 转发给云端 Runtime。
- 默认调用云端 `AgentkitAgentServerApp` 的 `/invoke` 兼容入口；该入口会在需要时创建 session。
- 如果要强制验证原生 ADK SSE，可以把 `CLOUD_AGENT_CALL_PATH=run_sse`。

这条路线不需要 `state_delta.local_inbound_auth_ref`，也不使用本地 token registry；
云端 Runtime 依赖 `AgentkitAgentServerApp(enable_auth=True)` 保存 `inbound_auth`。

## 获取 user token

如果只想手动拿 User Pool access token：

```bash
uv run python oauth2_testapp.py
```

打开：

```text
http://127.0.0.1:8082
```

## user token 换 TIP token

把 workload name 写入 `.env`：

```dotenv
VE_IDENTITY_WORKLOAD_NAME=<your_workload_identity_name>
```

```bash
uv run python exchange_user_token_for_tip.py --user-token "<user_pool_access_token>" --json
```

只输出 token：

```bash
TIP_TOKEN=$(uv run python exchange_user_token_for_tip.py --user-token '<user_pool_access_token>')
```

## 本地 import smoke

如果只是验证 `main.py` 能被云端入口导入，可以临时传入假的模型环境变量：

```bash
MODEL_AGENT_PROVIDER=openai \
MODEL_AGENT_NAME=test-model \
MODEL_AGENT_API_BASE=http://127.0.0.1 \
MODEL_AGENT_API_KEY=test \
uv run python -c "from main import app, root_agent, server; print(root_agent.name, bool(app), bool(server))"
```

## 验收标准

- `uv run python tests/test_mcp_authz_sample_contract.py` 通过。
- `app.py` 能作为本地登录 Web UI 入口。
- `main.py` 保留可选云端 AgentKit WebServer App 入口。
- `cloud_client_app.py` 能挂载 VeADK Web UI，并把登录后的请求代理到云端 Runtime。
- `oauth2_testapp.py` 能单独获取 User Pool access token。
- `exchange_user_token_for_tip.py` 能用 user token 换 TIP token。
