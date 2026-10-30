# CP 托管应用 CD OpenAPI 参考

本参考覆盖 CP OpenAPI `Version=2023-05-01` 的十个托管应用 Action，供
`scripts/managed_app.py` 在北京、柔佛生产环境使用。契约复核日期：2026-09-11。

## 目录

- [安全执行约定](#安全执行约定)
- [Action 与请求契约](#action-与请求契约)
- [CreateManagedApp 请求体](#createmanagedapp-请求体)
- [TriggerManagedAppDeploy 请求体](#triggermanagedappdeploy-请求体)
- [状态与验收流程](#状态与验收流程)

## 安全执行约定

- 所有命令仅通过 `client_from_env` 访问 `cn-beijing` / `ap-southeast-1` 生产白名单；
  不存在 pre 或自定义 endpoint 目标。
- `create`、`deploy`、`scale`、`rollback`、`cancel`、`delete` 都是写操作：先运行
  `--dry-run`，确认 Action、region、目标 ID 和脱敏后的 Body，再加 `--yes`。
- 写操作超时的结果可能不明确。不要自动重试；先执行 `records` 或在控制台检查应用状态。
- `delete` 默认只删除 CP 应用记录；只有显式指定 `--delete-cluster-resources` 才发送
  `DeleteClusterResourceOrNot=true`。未加 `--force` 时必须原样输入 App ID 二次确认。
- 请求文件可能包含镜像密码或环境密钥，应设置 `chmod 600`，不要提交，不要通过
  `--body-json` 留在 shell 历史中。所有默认输出都会递归脱敏。
- `logs` 始终脱敏，不提供原始日志输出开关。

## Action 与请求契约

| 子命令 | Action | 请求字段 |
|---|---|---|
| `create` | `CreateManagedApp` | `WorkspaceId`, `MetaInfo`, `BasicConfig`; 可选 `AdvancedConfig`, `EnvConfig`, `ReleaseStrategy`, `EnvType`, `Autoscalers` |
| `deploy` | `TriggerManagedAppDeploy` | `WorkspaceId`, `AppId`, `BasicConfig`, `AdvancedConfig`; 可选 `Description`, `ReleaseStrategy`, `Autoscalers` |
| `scale` | `TriggerManagedAppScaling` | `WorkspaceId`, `AppId`, `NewScale`; 可选 `Description`, `DeployResourceType=K8sYaml`, `ScaleType=ScaleUp|ScaleDown` |
| `rollback` | `TriggerManagedAppRollback` | `WorkspaceId`, `AppId`, `TargetChangeRecordId`; 可选 `Description` |
| `records` | `ListManagedAppChangeRecords` | `WorkspaceId`, `AppId`, `PageNumber`, `PageSize`; 可选 `Filter.Ids/Types/Statuses` |
| `cancel` | `CancelManagedAppChangeRecord` | `WorkspaceId`, `AppId`, `TargetChangeRecordId` |
| `steps` | `ListManagedAppChangeSteps` | `WorkspaceId`, `AppId`, `ChangeRecordId` |
| `pods` | `ListManagedAppPods` | `WorkspaceId`, `AppId`, `ChangeRecordId` |
| `logs` | `GetManagedAppPodLog` | `WorkspaceId`, `AppId`, `ChangeRecordId`, `PodName`; 可选 `LineNumber`（1..500） |
| `delete` | `DeleteApp` | `WorkspaceId`, `Id`; 可选 `DeleteClusterResourceOrNot=true` |

`create` / `deploy` 必须且只能使用 `--body-file` 或 `--body-json` 中的一种。脚本从
CLI 注入规范化后的 `WorkspaceId` / `AppId`；若 payload 已有不同值，会在发请求前拒绝。

## CreateManagedApp 请求体

最小结构从 `examples/managed-app-create.json` 复制。公开契约中的关键字段如下：

- `MetaInfo`（必填）
  - `Name`：应用标识。
  - `DisplayName`：展示名称。
  - `UserRoles`：用户/用户组与角色绑定数组。`RoleNames` 常见值为
    `Administrator`、`Developer`、`Tester`、`Operator`、`ReadOnly`；用户项使用
    `User.AccountId`，可选 `User.UserId`。
  - `AppStack`：可选，`Java|Other`。
  - `DeployType`：托管容器应用使用 `K8sYaml`。
- `BasicConfig`（必填）
  - `DeployType`：公开托管镜像路径使用 `Image`。
  - `ImageConfig`：镜像地址 `Image`、镜像类型 `ImageType=CR|Custom`；自定义仓库可带
    `ImageCredential.Username/Password`，该密码会在输出中脱敏。
  - `VersionNumber`：可选，1..63 个小写字母、数字、点或连字符。
  - `UseCustomSpecification` + `Specification`：标准规格使用
    `UseCustomSpecification: false`，`Specification` 填 `InstanceNumber`（>= 0）以及
    **数值型** `CPU`（单位 Core，如 `0.5`）、`Memory`（单位 Gi，如 `1`）。不要用
    `CPURequest`/`MemoryRequest` 等字符串字段，否则服务端会报
    `InvalidParameter: default specification missing resource value`。自定义 request/limit
    规格改用 `UseCustomSpecification: true` + `CustomSpecification`。
  - `AppServices`：可选的服务访问配置。
- `AdvancedConfig`（可选）：启动命令/参数、环境变量、健康检查、存储、服务访问权限、
  可观测性、探针、优雅下线、PDB 等。嵌套条件最终由服务端校验。
- `EnvConfig`（已有部署集群场景）：`DeployResourceId`、环境 `Name`，可选 `Namespace` 和
  `DeployResourceType=K8sYaml`。
- `EnvType`：公开 API 使用已有部署集群时为 `DeployCluster`。
- `ReleaseStrategy`：容器场景公开支持 `Type=Rolling`。
- `Autoscalers`：随本次部署创建或更新的 HPA 配置数组。

示例使用占位值，必须替换账户、用户、部署资源、镜像等字段：

```bash
python3 scripts/managed_app.py create \
  --workspace-id <WS_ID> \
  --body-file examples/managed-app-create.json \
  --dry-run
```

## TriggerManagedAppDeploy 请求体

部署 body 必须包含 `BasicConfig` 和 `AdvancedConfig`。可从现有应用配置或受控模板生成；
`AppId` 和 `WorkspaceId` 由命令行注入，不要依赖文件中的目标。可选字段为
`Description`、`ReleaseStrategy`、`Autoscalers`。

```json
{
  "BasicConfig": {
    "DeployType": "Image",
    "ImageConfig": {"Image": "registry.example.invalid/team/app:v2", "ImageType": "Custom"},
    "VersionNumber": "v2",
    "UseCustomSpecification": false,
    "Specification": {"InstanceNumber": 2, "CPU": 0.5, "Memory": 1}
  },
  "AdvancedConfig": {},
  "Description": "deploy v2",
  "ReleaseStrategy": {"Type": "Rolling"}
}
```

先把 JSON 保存为权限 `600` 的临时文件，再执行：

```bash
python3 scripts/managed_app.py deploy --workspace-id <WS_ID> --app-id <APP_ID> \
  --body-file /secure/path/deploy.json --dry-run
```

## 状态与验收流程

变更记录状态：`Pending`、`Running` 为非终态；`Succeeded`、`Failed`、`Canceled` 为终态。
响应中可能出现 `NotDeploy`，表示尚未部署，不能作为成功证据。变更步骤状态为
`Pending|Consumed|Running|Succeeded|Failed|Canceled|Cancelling`。当记录已 `Canceled` 但仍有
步骤处于 `Cancelling` 时，只能报告“记录终态、取消尚未完全收敛”。

创建返回 App ID；deploy/scale/rollback 返回新 ChangeRecord ID。响应只证明请求被接受，
容器部署成功必须依次收集：

```text
mutation accepted
  -> records: 找到目标记录并等到 Succeeded | Failed | Canceled
  -> steps: 检查有序步骤，不能有 Failed/Cancelling 等未收敛状态
  -> pods: 确认预期 Pod 数量及状态
  -> logs: 确认日志可读取且关键业务行为正常（默认脱敏）
```

常用命令：

```bash
python3 scripts/managed_app.py records --workspace-id <WS_ID> --app-id <APP_ID> --all
python3 scripts/managed_app.py steps --workspace-id <WS_ID> --app-id <APP_ID> \
  --change-record-id <RECORD_ID> --record-status Succeeded
python3 scripts/managed_app.py pods --workspace-id <WS_ID> --app-id <APP_ID> \
  --change-record-id <RECORD_ID>
python3 scripts/managed_app.py logs --workspace-id <WS_ID> --app-id <APP_ID> \
  --change-record-id <RECORD_ID> --pod-name <POD_NAME> --line-number 200
```

契约来源：火山引擎持续交付 OpenAPI 文档
<https://www.volcengine.com/docs/6461/1277764> 及同版本公开 IDL/校验行为。运行时只依赖本 skill
目录和 Python 标准库（TLS 可选使用 `certifi`），不依赖任何服务端源码 checkout。
