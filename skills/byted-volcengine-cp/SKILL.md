---
name: byted-volcengine-cp
description: 在火山引擎或 BytePlus 持续交付（CP）的生产环境管理 CI/CD 全生命周期，包括工作区、CI 流水线与运行日志、触发器、自定义步骤、服务连接、部署资源和 CD 托管应用。支持生产地域 cn-beijing 与 ap-southeast-1。当用户明确要求操作线上、生产或 prod 的 CP CI/CD、流水线、构建、部署、工作区、Webhook、触发器、自定义步骤、服务连接、部署资源、托管应用、运行状态或日志时使用。仅支持生产环境；不得用于 pre、预发或测试环境。
---

# CP 生产环境 CI/CD 管理

## 范围与路由

仅通过 `cp_api.client_from_env` 访问固定白名单中的生产 endpoint。API 版本为
`2023-05-01`，签名为 HMAC-SHA256 Signature V4，签名 service 固定为 `cp`。
拒绝 pre 地域或 pre 工作区引用，不允许通过环境变量覆盖 endpoint、签名 region 或 service。

| 领域 | CLI | Action |
|---|---|---|
| 工作区 | `create_workspace.py` / `workspace.py` / `cleanup.py workspace` | `CreateWorkspace`, `ListWorkspaces`, `UpdateWorkspace`, `DeleteWorkspace` |
| 流水线 | `create_pipeline.py` / `list_pipelines.py` / `update_pipeline.py` / `bulk_update_pipelines.py` / `cleanup.py pipeline` | `CreatePipeline`, `ListPipelines`, `UpdatePipeline`, `DeletePipeline` |
| 运行 | `run_pipeline.py` / `get_status.py` / `cancel_run.py` | `RunPipeline`, `ListPipelineRuns`, `ListStages`, `CancelPipelineRun` |
| taskRun 与日志 | `task_run.py` / `get_logs.py` | `ListTaskRuns`, `GetTaskRunLog`, `GetTaskRunLogDownloadURI` |
| 人工卡点 | `approve_task.py` | `DoTaskAction` |
| 构建集群 | `cp_api.list_agent_pools` | `ListAgentPools` |
| 触发器 | `trigger.py` | `CreatePipelineWebhookURL`, `CreateTrigger`, `ListTriggers`, `UpdateTrigger`, `DeleteTrigger` |
| 自定义步骤 | `component_step.py` | `ListComponentStep`, `CreateComponentStep`, `UpdateComponentStep`, `UpgradeComponentStep`, `DeleteComponentStep` |
| 服务连接 | `service_connection.py` | `CreateServiceConnection`, `UpdateServiceConnection`, `GetServiceConnection`, `ListServiceConnections`, `DeleteServiceConnection` |
| 部署资源 | `deploy_resource.py` | `CreateDeployResource`, `ListDeployResources`, `UpdateDeployResource`, `DeleteDeployResource` |
| 托管应用 | `managed_app.py` | 十个已审核的托管应用 Action，详见参考文件 |

## 生产地域与凭证

| `--region` | 平台 | endpoint | 签名 region | service | 公共 agentPool |
|---|---|---|---|---|---|
| `cn-beijing` | 火山引擎 | `cp.cn-beijing.volcengineapi.com` | `cn-beijing` | `cp` | `public/prod-v2-public` |
| `ap-southeast-1` | BytePlus | `cp.ap-southeast-1.byteplusapi.com` | `ap-southeast-1` | `cp` | `public/prod-v2-public` |

北京优先读取官方 SDK 约定的 `VOLC_ACCESSKEY` / `VOLC_SECRETKEY`，柔佛优先读取
`BYTEPLUS_ACCESSKEY` / `BYTEPLUS_SECRETKEY`。两个地域也都支持专用的
`CP_ACCESS_KEY` / `CP_SECRET_KEY`。每次只设置一组完整凭证；不要把凭证写入请求文件、命令参数、
Skill 目录、日志或共享文档。

只做只读连通性检查：

```bash
python3 scripts/cp_api.py ping cn-beijing
python3 scripts/cp_api.py ping ap-southeast-1
```

## 生产安全规则

1. 默认只读。用户明确授权生产写操作后，先运行对应命令的 `--dry-run`，核对 Action、Region、目标
   ID、范围和脱敏请求。对于非删除类生产 mutation，若 dry-run 与用户意图完全一致，在同一轮自动增加
   `--yes` 执行，无需再次确认；任一项不一致时停止执行并说明差异。
2. 删除操作必须在 dry-run 后展示 Action、Region 和精确目标 ID，等待用户再次确认后才能增加
   `--yes`。delete 命令还要求原样输入目标 ID；仅用户明确要求的非交互删除流程使用 `--force`。
   用户最初提出删除不等同于看到 dry-run 后的再次确认。
3. 写请求超时后结果不明确，禁止自动重试；先调用对应 list/get API 或控制台确认实际状态。
4. JSON/YAML 请求体中的显式目标必须由 CLI 注入或与 CLI 一致；冲突时在网络调用前拒绝。
5. 始终验证 TLS。不要增加跳过证书验证、任意 endpoint 或签名 service 的覆盖入口。
6. 默认递归脱敏 Credential、token、password、AK/SK、kubeconfig、脚本/YAML、Webhook URL 和日志
   URI。日志没有原文输出开关；敏感 URL 仅可用 `--output-file` 写入 mode `0600` 文件。
7. `ListDeployResources` 固定发送 `HideKubeconfig=true`。删除账号级服务连接或部署资源前，检查其他
   工作区、流水线和应用的引用。
8. mutation 返回 ID 只表示请求已接受。必须继续查询资源或运行状态，不能把 API `Code=0` 当成
   最终成功。

## 常用工作流

### 工作区与流水线

```bash
python3 scripts/workspace.py list --region cn-beijing --all --json
python3 scripts/create_workspace.py --region cn-beijing --name <NAME> --dry-run
python3 scripts/create_pipeline.py --region cn-beijing --workspace-id <WS_ID> \
  --name <NAME> --spec-file examples/exec-cmd.yaml --auto-agent-pool --dry-run
python3 scripts/list_pipelines.py --region cn-beijing --workspace-id <WS_ID> --all --json
python3 scripts/update_pipeline.py --region cn-beijing --workspace-id <WS_ID> \
  --pipeline-id <PID> --spec-file <SPEC.yaml> --dry-run
python3 scripts/run_pipeline.py --region cn-beijing --workspace-id <WS_ID> \
  --pipeline-id <PID> --dry-run
```

上述非删除命令的 dry-run 完全匹配用户授权时，在同一轮给原命令增加 `--yes` 执行。`--workspace-id` 支持纯 32 位 ID、
`北京prod<32hex>` 或 `柔佛prod<32hex>`；任何明确的 pre 引用都会被拒绝。

### 运行与日志

```bash
python3 scripts/get_status.py --region cn-beijing --workspace-id <WS_ID> \
  --pipeline-id <PID> --max 10
python3 scripts/task_run.py list --region cn-beijing --workspace-id <WS_ID> \
  --pipeline-id <PID> --run-id <RUN_ID> --task-id <TASK_ID> --all --json
python3 scripts/get_logs.py --region cn-beijing --workspace-id <WS_ID> \
  --pipeline-id <PID> --run-id <RUN_ID>
python3 scripts/task_run.py download-uri --region cn-beijing --workspace-id <WS_ID> \
  --pipeline-id <PID> --run-id <RUN_ID> --task-id <TASK_ID> \
  --task-run-id <TASK_RUN_ID> --step-name <STEP> --output-file /secure/path/log-uri.txt
```

状态 `InProgress` 等同 `Running`；`Canceling` 只证明取消请求已生效。长时间 `Queued` 且无日志通常
表示调度或资源等待，不得当作成功证据。

### 触发器与账号级资源

首次构造请求时按任务阅读：

- [workspace-run-log.md](references/workspace-run-log.md)
- [trigger-component-step.md](references/trigger-component-step.md)
- [global-resources.md](references/global-resources.md)

```bash
python3 scripts/trigger.py list --region cn-beijing --workspace-id <WS_ID> \
  --pipeline-id <PID> --all --json
python3 scripts/component_step.py list --region cn-beijing --custom --all --json
python3 scripts/service_connection.py list --region cn-beijing --all --json
python3 scripts/deploy_resource.py list --region cn-beijing --workspace-id <WS_ID> --all --json
```

### 托管应用 CD

执行前阅读 [managed-app-cd.md](references/managed-app-cd.md)。create/deploy/scale/rollback/delete 均先
使用 `--dry-run`；create/deploy/scale/rollback 完全匹配用户授权时同轮增加 `--yes`，delete 等待用户
再次确认后才增加 `--yes`。mutation 后依次验证：

已审核 Action：`CreateManagedApp`、`TriggerManagedAppDeploy`、`TriggerManagedAppScaling`、
`TriggerManagedAppRollback`、`ListManagedAppChangeRecords`、`CancelManagedAppChangeRecord`、
`ListManagedAppChangeSteps`、`ListManagedAppPods`、`GetManagedAppPodLog`、`DeleteApp`。

```text
records 终态 Succeeded
  -> steps 无 Failed/Cancelling
  -> pods 数量与状态符合预期
  -> logs 可读取且关键业务行为正常
```

`Canceled` record 若仍有 `Cancelling` step，不得称取消已完全收敛。

## 流水线 Spec 与组件元数据

创建或修改流水线 spec 前阅读
[pipeline-spec-authoring.md](references/pipeline-spec-authoring.md)。不要分发从内部数据库或服务端源码生成的
组件快照；使用生产 OpenAPI 查询当前账号可见的系统步骤。

```bash
python3 scripts/component_step.py list --region cn-beijing --builtin --all --json
```

手写 step 使用 `component` + `inputs`，不要使用组件渲染后的内部 `image` + `script` 形态。

## 文件索引

- `scripts/cp_api.py`：固定生产路由、Signature V4、地域解析、分页、脱敏和安全文件 helper。
- `scripts/openapi_common.py`：Mutation 门禁、错误处理和敏感输出 helper。
- `scripts/`：每个公开 Action 的显式 CLI；不存在任意 `--action` 执行入口。
- `references/`：按任务按需读取的详细公开契约和编写指南。
- `examples/`：只含合成占位值的请求和流水线模板。
