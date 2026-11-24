# 03 Queue Cloud：平台托管队列

此例为进阶模式，使用 AgentKit 平台托管的 Cloud 队列。模型 Runtime 执行对话，会话与编排服务中的托管 Dispatcher 消费工具 Work、调度和回收云 Sandbox。

## 进入项目并配置 uv

从仓库根目录执行。后面的命令均在 `03_queue_cloud_mode/` 中运行：

```bash
cd python/01-tutorials/08-agentkit-infra/agent_infra/advanced/03_queue_cloud_mode
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r ../../requirements.txt --default-index https://mirrors.aliyun.com/pypi/simple/

test -f ../../config.yaml ||
  install -m 600 ../../config.yaml.example ../../config.yaml
```

编辑 `agent_infra/` 下的 `../../config.yaml`，填写账号 AK/SK、地域、模型 ID、模型地址及 `harness.model.api_key_name`（方舟 Key 名称）。使用环境变量提供 AK/SK 时，将 YAML 中的对应字段留空。确认目标账号和地域已开通平台托管队列能力。

## 逐步创建资源

按顺序执行以下命令。每步都可加 `--dry-run` 查看计划。实际执行会创建计费资源。

### 1. CreateRoute

```bash
python run.py create-route
```

为后续 APIG 会话准备 Endpoint。已有 Ready Endpoint 时复用；有多个时设置 `environment.endpoint_id`，没有时设置 `environment.apig_gateway_id` 后创建。

### 2. CreateEnvironment（Cloud）

```bash
python run.py create-environment
```

创建 `Config.Type=Cloud` 的 Environment，等待 Environment 为 `Active`、平台 Sandbox 为 `Ready`。

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

为本轮 Endpoint 和 Environment 签发 Environment API Key。明文保存在本模式私有的 `../../.local/queue-cloud/environment-key.json`，供 APIG 会话调用使用；`cleanup` 成功后移除。

## 创建会话与流式对话

```bash
python run.py create-session
python run.py run-sse --prompt "请只回复 QUEUE_CLOUD_OK"
python run.py run-sse --prompt "上一轮我要求你回复什么？只输出标记。"
```

`create-session` 通过 APIG 调用 `POST /v1/sessions`；`run-sse` 向 `/events` 提交消息，再按回执序号订阅 `/events/stream`。Dispatcher 位于平台的会话与编排服务中，无需单独部署。

要验证平台消费了 Work，发送「用 bash 执行 `echo QUEUE_CLOUD_SANDBOX_OK`，只回复真实命令输出」。检查 `user.tool_result.tool_use_id` 与 `agent.tool_use.id` 相同、`is_error` 为 `false`，且工具结果包含 `QUEUE_CLOUD_SANDBOX_OK`。Sandbox `Ready` 只代表模板就绪。

## 在线验收：工具执行后立即删除会话

先完成上一轮 `python run.py cleanup`，再在本目录、已激活的虚拟环境中运行：

```bash
python accept_tool_delete.py --timeout 1200 --interval 3
```

脚本按上述步骤创建独占的本轮资源。在收到与 `agent.tool_use.id` 匹配、包含随机标记且 `is_error=false` 的真实 `user.tool_result` 后，立即向 APIG 发送 `DELETE /v1/sessions/{id}`，不等待模型最终回复、不预先归档。

随后每隔 3 秒先查询会话，再尝试删除本轮 Sandbox 资源，记录 `terminated`、`409 ResourceInUse`、首次会话 `404`、资源删除受理及资源删除完成。只有观测到会话 `404` 不晚于资源删除受理，且资源已删除、其余本轮资源已清理，才报告通过。时间来自客户端观测，受轮询间隔和请求耗时影响，不能当作服务端精确状态变化时间。

报告位于 `../../.local/queue-cloud/tool-delete-acceptance.json`，不包含凭据。超时不会伪报成功，也不会撤销本轮 Key；保留状态并继续观测：

```bash
python accept_tool_delete.py --resume --timeout 1200 --interval 3
```

恢复模式不再发送模型消息。验收会删除本轮独占资源，保留共享 Route 和 IAM 角色。

2026-11-24 北京线上实测通过：以收到真实工具成功结果为起点，约 0.002 秒发送会话删除，0.126 秒收到 `session_deleted`；首次资源删除返回 `409 ResourceInUse`，3.614 秒首次观测到会话 `404`，3.787 秒资源删除受理，23.214 秒资源删除完成。其余本轮资源清理成功，Key 文件已移除。本次使用 3 秒轮询，只证明这一轮的观测时序，不构成回收时限保证。

## 清理资源

```bash
python run.py cleanup --dry-run
python run.py cleanup
```

`cleanup` 按顺序删除 APIG Session、Environment API Key、模型 Runtime 和 SessionStore，再回收 Cloud Sandbox、删除 Environment 并归档 Harness。Route 与 IAM 角色保留。创建或清理中断后，保留 `../../.local/queue-cloud/resources.json`，修复错误后重跑清理命令。

调用过工具的会话需要等待平台回收派发记录。若删除请求成功但会话一直是 `terminated`，说明清理还没完成。保留状态文件和本轮 Environment API Key，待平台完成回收后重跑 `python run.py cleanup`；持续超时可提供会话 ID 供平台排查。
