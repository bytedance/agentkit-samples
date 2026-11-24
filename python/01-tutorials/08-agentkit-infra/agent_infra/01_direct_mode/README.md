# 01 Direct：Harness App 直连

本例使用 AgentKit 控制面创建 Cloud Environment 和 Runtime，随后直连 AgentKit CLI 的 Harness App 创建 Session、流式对话。会话保存在 Harness App，无需创建 Deployment 或 Environment API Key。

## 进入项目并配置 uv

从仓库根目录执行。后面的命令均在 `01_direct_mode/` 中运行：

```bash
cd python/01-tutorials/08-agentkit-infra/agent_infra/01_direct_mode
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r ../requirements.txt --default-index https://mirrors.aliyun.com/pypi/simple/

test -f ../config.yaml ||
  install -m 600 ../config.yaml.example ../config.yaml
```

编辑 `agent_infra/` 下的 `../config.yaml`，填写账号 AK/SK、地域、模型 ID 和模型地址。使用环境变量提供 AK/SK 时，将 `volcengine.access_key` 和 `volcengine.secret_key` 留空。Runtime 执行角色需要方舟模型访问和工具实例管理权限。

## 逐步创建资源

每步对应一条命令。加 `--dry-run` 可查看该步的调用计划，无需配置凭据，也不会创建资源。实际执行会创建计费资源。

### 1. CreateRoute（可选）

```bash
python run.py create-route
```

已有 Endpoint 时复用；有多个时设置 `environment.endpoint_id`，没有时设置 `environment.apig_gateway_id` 后调用 `CreateRoute`。Direct 会话走 Runtime Endpoint，因此可以跳过这一步。

### 2. CreateEnvironment（Cloud）

```bash
python run.py create-environment
```

创建 `Config.Type=Cloud` 的 Environment，等待 Environment 为 `Active`、Sandbox 为 `Ready`，保存 Sandbox `ToolId`。Cloud Sandbox 镜像需支持 Harness App 使用的 AIO Sandbox 接口。

### 3. CreateSessionStore

```bash
python run.py create-session-store
```

创建 `SERVERLESS_PG` 类型的 SessionStore，等待 `Ready`，保存 `SessionStoreId`。

### 4. CreateRuntimeTemplate

```bash
python run.py create-runtime-template
```

准备 IAM 执行角色，用 `SessionStoreId` 和 `HARNESS_SANDBOX_TOOL_ID` 创建 Runtime，再用 `GetRuntime` 等待 `Ready`。如果目标环境的默认镜像没有提供 Harness App，可设置 `runtime_template.image_url`。自建镜像的启动命令须能启动 `harness_app.server`，使用默认配置时监听 `8000` 并响应 `/ping`。

## 创建会话与流式对话

```bash
python run.py create-session
python run.py run-sse --prompt "请只回复 DIRECT_OK"
python run.py run-sse --prompt "上一轮我要求你回复什么？只输出标记。"
```

`create-session` 使用 `GetRuntime` 返回的 Runtime Key，先查询 `/list-apps`，再调用 `POST /apps/harness_agent/users/{user}/sessions/{id}`。两次 `run-sse` 复用同一会话，向 Runtime `POST /run_sse`。

要验证云沙箱，发送「用 Execute 在沙箱里运行 `echo DIRECT_SANDBOX_OK`，只回复真实命令输出」，并在 SSE 中核对 `functionCall` 和 `functionResponse`。

## 清理资源

```bash
python run.py cleanup --dry-run
python run.py cleanup
```

清理按依赖倒序执行：

1. 通过 Runtime 删除 Harness App Session。
2. 调用 `DeleteRuntime`，确认 Runtime 已删除后再调用 `DeleteSessionStore`。
3. 调用 `DeleteEnvironmentResource` 回收已记录的 Cloud Sandbox 资源，再调用 `DeleteEnvironment`。若创建中断时还未记录 Sandbox，Cloud Environment 的删除流程负责回收它所属的资源。

清理可在任意创建步骤后运行，只处理 `../.local/direct/resources.json` 记录的本轮资源。保留账号级 Route 和 IAM 角色，因为其他应用可能在使用。清理中途失败时，保留状态文件，修复错误后重跑 `python run.py cleanup`；不要先删除状态文件。如创建请求超时且未记录 ID，先在控制台按状态文件中的资源名称检查是否已经创建，再决定是否重试，尤其是 `CreateSessionStore`。
