# 02 Queue SelfHosted：自托管 Dispatcher

会话和对话通过 APIG 访问 AgentKit 会话服务；工具 Work 由自托管 Dispatcher 消费。此例内置 AgentKit Sandbox 后端，部署实现在 `../common/dispatcher.py`，无需其他教程目录。

## 进入项目并配置 uv

从仓库根目录执行。后面的命令均在 `02_queue_selfhost_mode/` 中运行：

```bash
cd python/01-tutorials/08-agentkit-infra/agent_infra/02_queue_selfhost_mode
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r ../requirements.txt --default-index https://mirrors.aliyun.com/pypi/simple/

test -f ../config.yaml ||
  install -m 600 ../config.yaml.example ../config.yaml
```

编辑 `agent_infra/` 下的 `../config.yaml`，填写账号 AK/SK、地域、模型 ID、模型地址及 `harness.model.api_key_name`（方舟 Key 名称）。使用环境变量提供 AK/SK 时，将 YAML 中的对应字段留空。Dispatcher 的连接信息由脚本从本轮运行状态提供。

## 逐步创建资源

按顺序执行以下命令。每步都可加 `--dry-run` 查看计划。实际执行会创建计费资源。

### 1. CreateRoute

```bash
python run.py create-route
```

为后续 APIG 会话准备 Endpoint。已有 Ready Endpoint 时复用；有多个时设置 `route.endpoint_id`，没有时设置 `route.apig_gateway_id` 后创建。

### 2. CreateEnvironment（SelfHosted）

```bash
python run.py create-environment
```

创建 `Config.Type=SelfHosted` 的 Environment，等待 `Active`。工具 Sandbox 由后续部署的 Dispatcher 按需启动。

### 3. CreateHarness

```bash
python run.py create-harness
```

保存模型、工具和 Agent Loop 配置，记录 `HarnessId` 供创建会话使用。

### 4. CreateSessionStore

```bash
python run.py create-session-store
```

创建 `SERVERLESS_PG` 类型的 SessionStore，等待 `Ready` 并记录 `SessionStoreId`。

### 5. CreateRuntimeTemplate

```bash
python run.py create-runtime-template
```

准备 IAM 执行角色，用 `SessionStoreId` 创建模型 Runtime，再用 `GetRuntime` 等待 `Ready`。

### 6. CreateAPIKey

```bash
python run.py create-api-key
```

为本轮 Endpoint 和 Environment 签发 Environment API Key。明文保存在本模式私有的 `../.local/queue-selfhost/environment-key.json`，供 Dispatcher 和 APIG 会话调用使用；`cleanup` 成功后移除。

## 启动 Dispatcher 并对话

```bash
python run.py dispatcher
python run.py create-session
python run.py run-sse --prompt "请只回复 SELFHOST_OK"
python run.py run-sse --prompt "上一轮我要求你回复什么？只输出标记。"
```

`dispatcher` 准备 Tool 模板并部署独立 Runtime 来消费同一环境的 Work。`create-session` 通过 APIG 调用 `POST /v1/sessions`；`run-sse` 向 `/events` 提交消息，再按回执序号订阅 `/events/stream`。

要验证沙箱，发送「用 bash 执行 `echo SELFHOST_SANDBOX_OK`，只回复真实命令输出」。检查 `user.tool_result.tool_use_id` 与 `agent.tool_use.id` 相同、`is_error` 为 `false`，且工具结果包含 `SELFHOST_SANDBOX_OK`。如需验证 Dispatcher 是否复用工具实例，再发一轮工具请求。

## 清理资源

先根据 `../.local/queue-selfhost/dispatcher.json` 停止并删除本轮 Dispatcher Runtime，再清理它创建的工具实例和 `owned: true` 的 Tool 模板。保留手动复用的模板。如果使用 K8s 等其他后端，先按对应教程停掉 Dispatcher 并清理本轮执行实例。然后执行：

```bash
python run.py cleanup --dry-run
python run.py cleanup
```

`cleanup` 按顺序删除 APIG Session、Environment API Key、模型 Runtime、SessionStore 和 Environment，最后归档 Harness。Route 与 IAM 角色保留。创建或清理中断时，保留 `resources.json` 和 `dispatcher.json`，按已记录的 ID 继续回收；确认后端已删除后再移走旧的 `dispatcher.json`。
