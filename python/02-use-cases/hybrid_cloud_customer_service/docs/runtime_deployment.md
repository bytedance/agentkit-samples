# 智能体运行时部署

本文说明如何在本地使用 AgentKit CLI 将本样例部署到混合云智能体运行时。部署模式使用 `hybrid`：镜像在本地构建并上传到目标 CR，运行时在云端创建。

## 1. 准备条件

- 已安装 `uv`；uv 会按项目配置获取 Python 3.12 并管理唯一的项目 `.venv`。
- 已获取当前云管理平台环境的 Region、Access Key ID 和 Secret Access Key。
- 本地网络可以访问当前环境的 AgentKit OpenAPI 和镜像仓库。
- 本地安装了 AgentKit CLI 可连接的 Docker daemon；仅有 `nerdctl` 兼容命令但没有 Docker socket 不满足 CLI 构建要求。

真实凭据只放在当前终端环境变量中。不要把 AK/SK、模型 API Key、Runtime API Key、内部域名或终端输出提交到仓库。
控制台登录用户名/密码与 Access Key ID/Secret Access Key 是两套凭据，不能相互替代。

## 2. 安装项目与 AgentKit CLI

先安装 uv。macOS / Linux（[uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)）：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

重新打开终端，在项目根目录执行：

```bash
uv sync --frozen --extra dev
uv run --frozen --extra dev agentkit --help
```

`uv sync` 自动创建/更新项目 `.venv`。不要再用 `python -m venv` 或 `pip install` 混装；所有本地命令统一通过 `uv run` 使用这一环境。仓库提交了 `uv.lock` 和由它导出的 `requirements.lock`。必须保留 `--frozen`，保证干净环境安装经过验证的依赖组合；Dockerfile 使用 `requirements.lock`，避免镜像构建时由 `pip` 重新解析传递依赖。`agentkit --help` 能正常显示命令列表，才继续配置目标环境。

修改 `pyproject.toml` 后，维护者必须同时刷新两份锁文件：

```bash
uv lock
uv export --frozen --no-hashes --no-dev --no-emit-project -o requirements.lock
```

## 3. 配置域名并预检 OpenAPI

向平台管理员获取当前用户环境的网关 IP 和完整域名。若环境没有可用的企业 DNS，需人工在本机 hosts 中配置以下域名；实际域名以平台交付信息为准：

```text
<gateway-ip> console.<environment-domain> openapi.<environment-domain>
<gateway-ip> minio.<environment-domain> terminal.<environment-domain> skills.<environment-domain>
```

macOS 修改 `/etc/hosts`，Linux 修改 `/etc/hosts`，Windows 修改 `C:\Windows\System32\drivers\etc\hosts`；该操作通常需要管理员权限。修改后先确认解析结果：

```bash
# Linux
getent hosts "openapi.<environment-domain>"

# macOS
dscacheutil -q host -a name "openapi.<environment-domain>"
```

本 POC 默认使用交付的 HTTP TOP；先按实际配置协议验证，不要使用 `-k`：

```bash
export AGENTKIT_OPENAPI_HOST='openapi.<environment-domain>'
export AGENTKIT_OPENAPI_SCHEME="${AGENTKIT_OPENAPI_SCHEME:-http}"
curl --fail --silent --show-error \
  --connect-timeout 10 \
  --max-time 20 \
  "${AGENTKIT_OPENAPI_SCHEME}://${AGENTKIT_OPENAPI_HOST}/ping"
```

预期返回包含 `{"message":"pong"}`。正式环境应显式设置 `AGENTKIT_OPENAPI_SCHEME=https`，此时必须通过系统 CA 校验。HTTP 返回 `308` 只表示发生了跳转，不能证明最终 HTTPS 链路可用。HTTPS 若出现自签名证书、域名不匹配或 `Kubernetes Ingress Controller Fake Certificate`，应修复 Ingress 的 TLS Secret 和证书链；`curl -k` 只能用于管理员诊断，不能作为用户部署方案。

## 4. 设置本地凭据

在当前终端设置变量。以下均为变量名，不要把真实值写回脚本：

```bash
export VOLCENGINE_ACCESS_KEY=<your-access-key>
export VOLCENGINE_SECRET_KEY=<your-secret-key>
export VOLCENGINE_REGION=<target-region>
```

AK/SK 的人工获取路径为：使用主账号登录平台，点击右上角用户账号，进入
**访问控制 → 密钥管理**，按平台安全规范创建或查看访问密钥。资源账号主要用于模型和算力
资源管理，不一定显示访问控制菜单。不要把控制台登录密码、模型 API Key 或 Runtime API Key
当作 AK/SK。

关闭终端后这些导出值不会自动保留。如果通过其他安全凭据工具注入环境变量，也可以直接复用。

以上变量用于 AgentKit 部署控制面。Model Name/API Base/API Key 属于 Runtime 数据面，不参与 OpenAPI 鉴权；但本 Demo 默认发布可直接使用的 live Runtime，因此 launch 前必须安全提供 API Key。样例的默认方舟 Model Name/API Base 由项目补齐；自定义/真实环境应显式覆盖完整三项。只有用户明确选择基础链路排障的 Demo 模式时才可省略。

## 5. 配置目标环境 OpenAPI

仓库提供 [configure_agentkit_cli.sh.example](../scripts/configure_agentkit_cli.sh.example)。它从当前终端读取 OpenAPI 域名和凭据，先重复 `/ping` 预检，再配置 AgentKit、IAM 和 CR：

```bash
export AGENTKIT_OPENAPI_HOST='openapi.<environment-domain>'
export AGENTKIT_OPENAPI_SCHEME='http'
```

`AGENTKIT_OPENAPI_HOST` 只填写域名，不含 `http://`、`https://`、路径或尾部空格。不同环境的域名可能不同，不要复制其他用户或演示环境的实际域名。
通常可按 `openapi.<environment-domain>` 组成 OpenAPI 域名。Runtime Region 可在运维端右上角
账户菜单进入 **关于**，查看“地域”；如果平台已经创建过 Runtime，也可以查看该 Runtime 的
环境变量 `REGION`。不要根据其他环境的 Region 猜测当前值。

本 POC 默认 `http`，脚本会显示安全警告。正式环境必须显式设置 `AGENTKIT_OPENAPI_SCHEME=https`，并提供匹配域名的可信证书。

脚本还会配置 Region、`hybrid` 部署方式以及当前终端提供的 AK/SK。凭据值不会出现在脚本或脚本输出中，但 AgentKit CLI 会把它们写入本机的全局配置；请按本机安全规范保护该配置。

## 6. 镜像仓库凭据

正常情况下不需要在 launch 前主动执行 `docker login`。AgentKit 会通过已配置的 CR OpenAPI：

1. 确认 `cr-basic`、`agentkit` 命名空间和目标 Repo。
2. 获取当次短期 CR 凭据。
3. 自动登录 Registry 并推送本次镜像。

若 launch 明确返回 `token expired`、`invalid token claims`、`unauthorized` 或
`authentication required`，说明本次实际使用的 Registry 临时凭据已失效或不可用。
此时人工刷新不是违规操作，而是必要恢复路径：

1. 打开 **产品与服务 → 镜像仓库 → cr-basic → 获取临时访问指令**。
2. 在当前 Docker 上下文执行页面给出的完整命令。
3. 确认 `Login Succeeded`，重新运行部署脚本。

临时密钥会过期，Docker 的 `config.json` 只表明“曾经登录”，不能证明令牌仍有效。
不要把完整命令或令牌粘贴到 Prompt，或保存到仓库、README、验证记录和工单。没有
出现上述真实鉴权错误时，不应把手工登录变成固定前置步骤。

## 7. 检查应用配置

复制公开模板生成本地配置：

```bash
cp agentkit.yaml.example agentkit.yaml
chmod 600 agentkit.yaml
agentkit config --config agentkit.yaml --show
```

确认以下项目：

- 应用名称和入口文件分别为 `hybrid_cloud_customer_service`、`agent.py`。
- Python 版本为 `3.12`。
- 部署模式为 `hybrid`。
- AgentKit 元数据中的项目依赖文件为 `requirements.txt`；自定义 Dockerfile 实际从锁定的 `requirements.lock` 安装镜像依赖。
- 公开模板的 `runtime_envs` 只有 `DEMO_MODE=live`；模型值由部署脚本从当前终端写入临时配置，不进入公开模板。
- `launch_types.hybrid` 显式包含 `cr-basic`、`agentkit` 和样例 Repo 名，避免通过公有云 STS 推导 `account_id`。

`agentkit.yaml` 已被仓库忽略，不要强制提交它。

自动部署脚本只接受本次显式确认的 `VOLCENGINE_REGION`，并写入
`launch_types.hybrid.region`。它会显示检测到的全局 Region，但不会静默采用：
CLI 历史默认值可能属于另一环境，曾导致 CreateRuntime 使用 `cn-sh` 并返回
`InvalidRegion`。AgentKit 0.5.5 也不会为已有项目配置可靠继承全局 Region。

## 8. 构建并部署

面向人工部署，推荐交互式入口：

```bash
./scripts/deploy_interactive.sh
```

它先要求显式输入目标 Region，再提供两种模型配置：

- 默认方舟：使用项目内置的 Model Name/API Base，只隐藏输入一次 API Key。
- 自定义 OpenAI-compatible 模型：依次输入 Model Name、API Base 和隐藏的 API Key。

输入只存在于当前部署进程，不写 `.env` 或仓库。默认值为
`MODEL_AGENT_NAME=deepseek-v4-pro-260425`、
`MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3`。

部署前还会按 Runtime Name 和本次 Region 查询已有实例。发现唯一同名 Runtime 时，
交互入口会要求确认：

- 选择“更新”后，本次临时配置绑定该 Runtime ID，launch 执行更新；
- 选择“创建独立 Runtime”后，直接输入新名称；脚本先按 Region 精确查重，再创建；
- 不会仅凭名称静默覆盖平台资源。

launch 成功后，脚本只将非敏感的 `launch_types.hybrid.runtime_name/runtime_id`
写回本地 `agentkit.yaml`，以便后续继续更新；模型值、Endpoint 和 API Key 不会写回。

非交互/CI 环境应由 Secret 管理工具显式注入完整值：

```bash
export VOLCENGINE_REGION='<target-region>'
export MODEL_AGENT_NAME='<model-name-or-endpoint-id>'
export MODEL_AGENT_API_KEY='<model-api-key>'
export MODEL_AGENT_API_BASE='<openai-compatible-base-url>'
./scripts/deploy_hybrid.sh
```

若平台已存在目标 Runtime，自动化环境还必须显式设置
`AGENTKIT_RUNTIME_ID='<runtime-id>'`；或者在已经核对唯一同名实例后设置
`AGENTKIT_REUSE_EXISTING_RUNTIME=1`。默认行为是停止，而不是覆盖。

底层脚本会把 API Base、Model Name、API Key 三项全部写入 launch 使用的临时 Runtime
配置；随后执行控制面配置、项目 Region 同步、应用配置校验、Docker SDK 检查、
`linux/amd64` 发布、状态查询和一次 live 调用。缺少 Region 或 API Key 时会在构建前
失败，不会静默降级。脚本不额外执行 `docker pull` 或预先 `docker login`；如果
launch 实际返回临时 Registry 凭据过期，会输出人工刷新登录的明确恢复路径。

AgentKit 0.5.5 会自动把项目 `.env` 中的所有赋值合并到 Runtime 环境。为防止本地 UI Key、控制面凭据或无关 Secret 被上传，部署脚本检测到非空 `.env` 会拒绝继续。模型变量应只导出到当前终端。脚本把它们写入项目目录中的临时 `0600` 配置；该文件被 `.gitignore` 和 `.dockerignore` 排除，并在退出时删除。

如用户明确只需验证构建、CR、Runtime、网关和 `/invoke` 基础链路，可显式选择：

```bash
AGENTKIT_DEPLOY_MODE=demo ./scripts/deploy_hybrid.sh
```

该结果必须标记为 Demo，不代表真实模型或平台能力验收完成。

如果全局 AgentKit 控制面已经配置，脚本会用只读 `runtime list` 验证并复用；如果
当前终端提供了完整的 OpenAPI Host、AK、SK，脚本会自动调用配置脚本。Region 始终
单独显式确认，避免复用错误的历史默认值。若访问 Docker Hub 超时，请先按企业规范
配置容器 Registry Mirror。

不建议直接用公开模板执行手动 launch，因为模板故意不包含模型 Secret。确需手动操作时，先复制一份权限为 `0600`、被 Git/Docker 排除的私有配置，在其中加入 live 模型变量，再执行：

```bash
./scripts/configure_agentkit_cli.sh.example
agentkit launch --config-file <private-live-config> --platform linux/amd64 --preflight-mode skip
agentkit status --config-file <private-live-config> --verbose
agentkit invoke --config-file <private-live-config> "退款多久到账？"
```

混合云交付的 AgentKit、IAM、CR 都走当前环境 OpenAPI，因此这里显式使用 `preflight-mode=skip`，避免 CLI 用公有云服务开通状态产生假阻塞。它不会跳过 `/ping`、AK/SK 的 `runtime list` 校验、Docker SDK 检查或部署后的 Runtime 状态验收。

首次部署通常需要 2～3 分钟。满足以下条件才视为成功：

1. `agentkit status` 显示 Runtime 为 `Ready`。
2. Runtime 日志没有镜像架构、依赖或环境变量启动错误。
3. 脚本最后的 `agentkit invoke`（或控制台在线测试调用 `/invoke`）能返回 live 最终回答。
4. 开启观测服务并重新发布后，平台 Trace 中存在对应 LLM Span、模型名、Token 和耗时。

显式 Demo 模式只需满足前三项的基础链路部分，不能满足第 4 项，也不能作为完整客户验收。

后续使用 `runtime update` 关联 Knowledge、Memory、Tool 或 MCP Toolset 时，还必须执行 `runtime release` 并等待 Runtime 再次进入 `Ready`。仓库中的 `scripts/bootstrap_platform.py` 已把关联、发布和等待封装为一个步骤。

安全盘点 Tool 时必须限定字段，例如：

```bash
agentkit tools list \
  --region <target-region> \
  --fields ToolId,Name,ToolType,Status
```

不要用无字段限制的 `agentkit tools list --output json|yaml`：AgentKit 0.5.5 会返回完整 Tool 环境变量，其中可能包含模型 API Key。若该输出已写入共享日志或工单，按组织安全规范轮换相关密钥。

本样例生产镜像必须使用 `linux/amd64`。Dockerfile 固定 Python 基础镜像的 amd64 平台摘要，发布参数也固定该架构，以兼容 Apple Silicon 上 AgentKit 0.5.5 使用的 Docker SDK 经典构建接口。需要独立检查镜像时可执行：

```bash
docker build --platform linux/amd64 -t hybrid-cloud-customer-service:latest .
```

构建日志应显示安装 `requirements.lock` 中的固定版本。如果日志中 `pip` 长时间反复尝试同一依赖的多个版本，先确认 Dockerfile 和两份锁文件来自当前提交，不要靠手工预拉基础镜像规避依赖解析问题。

交互部署会实时输出 Docker 构建和镜像推送详情，并以 `[docker]` 标记，包括 Dockerfile 步骤、依赖下载、架构警告、构建错误和各层推送状态；同一份输出也会保留给脚本做失败诊断。该模式只打开 Docker 组件的详细日志，不会把控制面请求或凭证相关信息切换到全局 DEBUG。

若 Apple Silicon 构建机报本地层为 `linux/arm64/v8`、目标为 `linux/amd64`，确认没有删除 Dockerfile 中默认值为 `linux/amd64` 的 `RUNTIME_PLATFORM`，且脚本仍传递 `--platform linux/amd64`。这是 AgentKit 0.5.5 的 Docker SDK 经典构建接口对本地跨架构缓存的兼容要求，不需要手工预拉镜像。升级 Python 基础镜像时必须重新确认新摘要对应 `linux/amd64`。

## 9. Live 模型数据面

默认部署在 launch 前解析并注入以下模型数据面变量：

- `DEMO_MODE=live`
- `MODEL_AGENT_NAME=deepseek-v4-pro-260425`：默认方舟值；自定义环境覆盖
- `MODEL_AGENT_API_KEY=<model-api-key>`
- `MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3`：默认方舟值；自定义环境覆盖。

自动脚本通过临时配置完成注入。生产环境若支持 Runtime Secret，建议在控制台的 Secret 配置中录入并重新发布，以获得平台级密钥管理。模型 API Key 不参与 AgentKit OpenAPI 的部署鉴权，也不应写入仓库中的 `agentkit.yaml.example`。

若此前显式部署了 Demo 或仍在使用旧版默认 Demo，重新设置上述终端变量并直接运行默认脚本即可更新为 live；也可在控制台修改环境变量/Secret 后重新发布。

## 10. 调试与观测

进入 **AgentKit → 智能体运行时 → 目标 Runtime → 快速调用**（部分版本称“在线测试”或“调用信息”），复制该 Runtime 自己的 Endpoint 和 API Key。不要使用模型 API Key、OpenAPI AK/SK 或另一个 Runtime 的 Key。

可以先在控制台在线测试，也可以启动本地 UI，并在顶部“连接配置”中填写 Runtime Endpoint 与 API Key：

```bash
./scripts/run_local_ui.sh
```

保存连接配置只表示 Endpoint/Key 已进入本地 BFF 内存。发送一条消息后，右上角状态才给出调用证据：

- `本地 Demo`：由本机 `demo_core` 处理，没有调用远端；
- `远端已配置 · 待调用验证`：尚未产生远端调用证据；
- `远端 Runtime · Demo`：已到达远端，但 Runtime 仍为 `DEMO_MODE=demo`；
- `远端 Runtime · Live`：已到达远端并进入 live Agent 数据面。

自动部署脚本现在默认创建“远端 Runtime + Live 数据面”。看到 `mode=demo` 说明目标是显式 Demo、旧版默认 Demo，或后来被改回 Demo；连接本身仍可能有效，但需要按第 9 节重新部署/发布 live 并等待 `Ready/Healthy`。

Demo 模式直接运行确定性 FastAPI，不创建 `AgentkitAgentServerApp`，因此不会调用模型，也不会产生平台 Agent/LLM Span、Token 或模型思考事件；响应中的 `trace-...` 是应用演示 ID，不是平台 Trace ID。

完成一次 live 请求后，在 **可观测 → Trace 分析** 中按 Runtime 名称和时间核对 Agent、Workflow、LLM 与 Tool Span。Runtime 创建或编辑时还需在“高级配置”中开启观测服务并重新发布。以 LLM Span 中的模型名称、Input/Output/Total Tokens 和耗时作为模型调用证据；不能把“存在 thought 文本”作为必选条件，因为模型可能不返回可展示的思考过程。

### Docker 直跑并接入平台可观测

不使用平台 Runtime 托管时，仍可使用同一镜像直接启动容器。将平台关联组件注入的非敏感
配置和人工取得的密钥保存在目标机器的 `0600` env 文件中，不要提交该文件：

```dotenv
DIRECT_CONTAINER_MODE=true
OTEL_SERVICE_NAME=<unique-service-name>
OTEL_RESOURCE_ATTRIBUTES=apmplus.business_carrier=agentkit_runtime

OTEL_TRACES_EXPORTER=otlp
OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://<collector>/<credential-path>/v1/traces

OTEL_METRICS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://<collector>/<credential-path>/v1/metrics

OTEL_LOGS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_LOGS_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://<collector>/<credential-path>/v1/logs

OTEL_METRIC_EXPORT_INTERVAL=60000
OTEL_PYTHON_LOG_LEVEL=INFO
```

```bash
chmod 600 /path/to/runtime.env
docker run -d --name hybrid-cloud-customer-service \
  --env-file /path/to/runtime.env \
  -p 18001:8000 \
  <registry>/<repository>:<tag>
```

验收至少包含：健康检查返回 200；`/invoke` 返回最终回答；Trace 中出现
`agent_server → workflow → agent → llm/tool`；运行时大盘调用数增加；日志页能按同一
`OTEL_SERVICE_NAME` 检索到带 TraceID 的应用日志。Trace 中存在 Token 但聚合大盘为 0 时，
应单独检查 Metrics 查询字段映射，不能据此否定 Trace 上报。

## 11. 查看状态与清理

```bash
agentkit status
```

仅在确认不再使用目标 Runtime 时执行：

```bash
agentkit destroy
```

`destroy` 会删除运行时及相关资源。执行前务必核对当前 Region、Runtime 名称和目标环境。
