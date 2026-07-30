# AgentKit 混合云企业智能客服 Demo

本样例从一个可调用真实模型的 Live Runtime 开始，再按路线图逐步接入 Knowledge、
Memory、会话、业务工具、Sandbox、MCP、Skills、A2A、身份安全、评测和 Trace。

## 第一步：交互部署 Live Runtime

首次部署不需要 Prompt，也不要求先配置 Codex Skill。确认 Docker Desktop/Engine
正在运行，并已安装 `uv`，然后在本 Demo 目录执行唯一入口：

```bash
./scripts/deploy_interactive.sh
```

脚本会依次完成：

1. 检测已有 AgentKit CLI 环境，允许复用或交互配置另一个 OpenAPI；
2. 隐藏输入目标环境 AK/SK，不要求提前 `export`；
3. 明确确认本次 Runtime Region，不静默复用历史默认值；
4. 默认方舟只隐藏输入模型 API Key，自定义模型才询问 Name 和 API Base；
5. 发现同名 Runtime 时，让用户确认更新或输入新名称创建独立实例；
6. 构建并发布 `linux/amd64` 镜像，等待 `Ready/Healthy`，完成一次 Live invoke。

交互输入的凭据不会回显、不会写入 `.env` 或仓库。新配置的控制面 AK/SK 会按
AgentKit CLI 的标准行为保存到本机 `~/.agentkit/config.yaml`；模型 Key 只进入临时
部署配置。launch 成功后只把非敏感的 Runtime Name/ID 保存到本地 `agentkit.yaml`，
供下次更新使用。

<details>
<summary><strong>首次环境准备：安装 uv、同步依赖和检查 Docker</strong></summary>

macOS / Linux：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

重新打开终端后执行：

```bash
uv --version
uv sync --frozen --extra dev
uv run --frozen --extra dev agentkit --help
docker info
```

项目只使用 uv 管理的 `.venv`。不要另建 venv，也不要向该环境混装 pip 依赖。
若企业 DNS 尚未配置，仍需按平台管理员提供的信息人工配置 hosts。

</details>

## 第二步：打开智能体建设路线图

Runtime 部署成功后启动本地路线图：

```bash
UI_PORT=18000 ./scripts/run_local_ui.sh
```

- 路线图：[http://127.0.0.1:18000/](http://127.0.0.1:18000/)
- 部署后 Chat：[http://127.0.0.1:18000/chat](http://127.0.0.1:18000/chat)

路线图提供 7 个建设阶段。每个阶段同时展示业务目标、平台动作、步骤文档、验收证据
和可复制的 Agent Prompt。首次 Runtime 已由交互脚本部署，因此 Runtime 阶段的
“验收首次部署”建议现在执行，用于补齐平台 Trace 和验收记录；“更新已有 Runtime”
只在以后修改代码、依赖、模型配置或组件关联时执行，现在可以跳过。后续 Prompt 再
继续创建、关联和验证平台能力。

基础组件必须按顺序执行：**创建并发布 Knowledge → 创建或复用 Memory → 同时关联
Runtime 并 release → 配置 Runtime Endpoint/Key → 运行 Knowledge/Memory 联合验证**。
路线图不会再在资源或关联缺失时提前提供联合验证 Prompt。

## 第三步：用项目 Skill 执行路线图 Prompt

仓库已经提供版本化的项目执行规范：

- [AGENTS.md](AGENTS.md)：智能编码 Agent 的项目入口；
- [agentkit-hybrid-cloud-demo](.agents/skills/agentkit-hybrid-cloud-demo/SKILL.md)：
  完整的安全、部署和验收规范；
- `docs/steps/`：各能力的客户操作步骤。

实际使用方式：

1. 把本 `hybrid_cloud_customer_service` 目录作为智能编码工具的项目根目录；
2. 在路线图中选择下一阶段并展开对应 Prompt；
3. 复制 Prompt，新建 Agent 任务并粘贴执行；
4. Prompt 会要求 Agent 先读取 `AGENTS.md` 和项目 Skill，再按步骤文档操作；
5. 遇到 hosts、控制台模型选择、上传文档或临时登录等人工动作时，由 Agent 单独提示。

不要求安装 Codex。任何能够读取仓库文件并执行终端命令的智能编码 Agent，都可以
直接遵循项目规范。不要把密码、AK/SK、模型 Key、Runtime API Key 或临时 Registry
Token 粘贴到 Prompt。

<details>
<summary><strong>可选：安装为 Codex 用户级 Skill</strong></summary>

如需在新 Codex 任务中直接发现 `$agentkit-hybrid-cloud-demo`：

```bash
./scripts/install_codex_skill.sh
```

仓库更新后，先查看 Skill 变更，再执行：

```bash
./scripts/install_codex_skill.sh --update
```

安装或更新后必须新建 Codex 任务。旧任务不会刷新 Skill 列表；不要自动替换成
其他相近或通用 Skill。

</details>

## 路线图与步骤文档

| 步骤 | 目标 | 详细文档 |
| --- | --- | --- |
| 00 | 验收或更新 Runtime、连接 Chat | [Runtime](docs/steps/00-runtime.md) |
| 01 | 创建或复用云搜索 Knowledge | [Knowledge](docs/steps/01-knowledge.md) |
| 02 | 创建或复用 MEM0 Memory | [Memory](docs/steps/02-memory.md) |
| 03 | 关联组件并重新发布 Runtime | [Runtime 关联](docs/steps/03-runtime-association.md) |
| 04 | 验证 Knowledge、跨会话记忆和用户隔离 | [Knowledge/Memory 验证](docs/steps/04-knowledge-memory-validation.md) |
| 05 | 验证 AIO Sandbox 与平台 MCP | [Sandbox/MCP](docs/steps/05-sandbox-mcp.md) |
| 06 | 发布、加载并执行 Skills 中心 Skill | [Skills](docs/steps/06-skills.md) |
| 07 | 验证 A2A 与身份权限 | [A2A/身份](docs/steps/07-a2a-identity-session.md) |
| 08 | 离线评测、平台 Trace 和发布验收 | [评测与可观测](docs/steps/08-evaluation-observability.md) |

步骤 06 的可发布业务 Skill 位于仓库共享目录
[`skills/byted-customer-service-compliance/SKILL.md`](../../../skills/byted-customer-service-compliance/SKILL.md)；
控制台直接上传默认包
[`skills/byted-customer-service-compliance.zip`](../../../skills/byted-customer-service-compliance.zip)；上传、关联与验证见该步骤文档。

步骤 07 的数据分析 A2A Runtime 使用独立交互入口
`./scripts/deploy_a2a_interactive.sh`：交互输入 Agent 名称、AgentCard 能力 ID 与模型配置后自动构建、发布并等待就绪。
首次 A2A 空间/AgentCard 登记仍需在控制台确认。A2A 中心是可登记多个 Agent 的治理与发现入口；
本 Demo 的投诉分析 Agent 只是默认验收目标。登记后执行 `./scripts/configure_a2a_peer_interactive.sh`，
手动输入 A2A 中心显示的服务地址和隐藏 Key；脚本会读取 AgentCard，自动取得 Agent 名称及
`skills[].id` 能力 ID，并安全写入主客服 Runtime 后自动 release。若 Card 声明多个能力，
脚本才会列出 ID 供选择。详情见 [A2A/身份](docs/steps/07-a2a-identity-session.md)。

> A2A 规范把 AgentCard 的能力列表命名为 `skills`，所以代码兼容保留
> `A2A_DATA_AGENT_SKILL_ID`；这里填写的是 `AgentCard.skills[].id`（例如
> `complaint-trend-analysis`），不是步骤 06 的 Skills 中心 Skill，也不是
> `SKILL_SPACE_ID` 或 Skills Sandbox。

同一步骤的身份安全验收使用另一个独立入口
`./scripts/deploy_oauth_interactive.sh`。它只创建或更新
`hybrid-cloud-customer-service-oauth`，不会替换主 Runtime 的 API Key 鉴权、Name/ID
或任何 Knowledge、Memory、Sandbox、MCP、Skills、A2A 关联。发布后使用
`./scripts/verify_oauth_interactive.sh --show-response`：脚本从用户池获取短期 Token，并直接以
`Authorization: Bearer <token>` 调用独立 OAuth Runtime；HTTP 200 和最终回答即为默认验收。
这不是另一套 OAuth 服务测试。需要演示网关拒绝行为时，再显式增加 `--negative-checks`
验证缺失和伪造 JWT；Client Secret 与 Token 均不打印、不落盘。
POC 认证域名仅支持 HTTP 时，部署脚本会为本次 OAuth 子进程启用 CLI 0.5.5 兼容校验；
正式环境仍必须使用 HTTPS。

`Runtime Ready` 只代表实例健康。完整验收还需远端 `mode=live` 的最终回答，以及平台
Agent/Workflow/LLM/Tool Trace。

<details>
<summary><strong>自动化 / CI：非交互变量方式</strong></summary>

仅自动化环境使用底层脚本。所有 Secret 应由 CI Secret 管理工具注入：

```bash
export AGENTKIT_OPENAPI_HOST='<openapi-domain>'
export AGENTKIT_OPENAPI_SCHEME='<http-or-https>'
export VOLCENGINE_ACCESS_KEY='<access-key>'
export VOLCENGINE_SECRET_KEY='<secret-key>'
export VOLCENGINE_REGION='<target-region>'
export MODEL_AGENT_NAME='<model-name-or-endpoint-id>'
export MODEL_AGENT_API_BASE='<openai-compatible-base-url>'
export MODEL_AGENT_API_KEY='<model-api-key>'
./scripts/deploy_hybrid.sh
```

若平台已有目标 Runtime，还应显式设置 `AGENTKIT_RUNTIME_ID`；默认不会覆盖同名实例。
详细说明见[智能体运行时部署](docs/runtime_deployment.md)。

</details>

<details>
<summary><strong>部署后连接 Chat</strong></summary>

从目标 Runtime 的“快速调用/在线测试/调用信息”获取该 Runtime 自己的 Endpoint 和
API Key，并只在本地终端设置：

```bash
export RUNTIME_ENDPOINT='<runtime-base-url>'
export RUNTIME_API_KEY='<runtime-api-key>'
UI_PORT=18000 ./scripts/run_local_ui.sh
```

在 `/chat` 发送新消息。只有 `远端 Runtime · Live` 加平台 Trace 才代表真实 Agent
数据面通过；`远端 Runtime · Demo` 只证明请求到达远端。

</details>

<details>
<summary><strong>开发、测试与更多文档</strong></summary>

```bash
uv run --frozen --extra dev pytest -q
uv run --frozen --extra dev ruff check .
DEMO_MODE=demo uv run --frozen client.py
```

- [Agent 内部实现与混合云开发手册](docs/agent_internal_implementation.md)
- [Runtime 部署](docs/runtime_deployment.md)
- [MCP 接入](docs/mcp_validation.md)
- [A2A 验证](docs/a2a_agent_validation.md)
- [评测与可观测](docs/evaluation_and_observability.md)
- [常见问题与排障](docs/troubleshooting.md)

</details>

## 代码许可

本项目采用开源许可证，详情请参考项目根目录下的 LICENSE 文件。
