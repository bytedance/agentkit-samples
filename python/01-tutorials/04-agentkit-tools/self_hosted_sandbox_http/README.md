# EnvironmentResource HTTP 示例

每个脚本新增 `--workspace-id <id>`，优先于 `HARNESS_INFRA_WORKSPACE_ID`
（兼容 `AGENTKIT_WORKSPACE_ID`）。Create/Get/List 在签名前发送 `WorkspaceId`，
轮询和所有分页使用同一选择器；响应内部保留 `workspace_id`。
省略/空值使用服务端唯一 ACTIVE DEFAULT。跨 Workspace Get 返回不存在，
NextToken 不能跨 Workspace 使用。缓存记录归属，跨 Workspace 请使用独立
`AGENTKIT_RESOURCE_STATE`。Update/Delete 仍按 ID 定位；云项目归属由服务端解析。

本目录通过 Volcengine/BytePlus TOP 签名入口或账号级 API Key 直连入口，演示
EnvironmentResource 的创建、查询、分页、更新和删除。

| 脚本 | Action | 用途 |
| --- | --- | --- |
| `01_create_environment_resource.py` | `CreateEnvironmentResource` | 创建资源并可选等待 `ready` |
| `02_get_environment_resource.py` | `GetEnvironmentResource` | 查询资源或恢复轮询 |
| `03_list_environment_resources.py` | `ListEnvironmentResources` | 筛选及遍历 `NextToken` |
| `04_update_environment_resource.py` | `UpdateEnvironmentResource` | 按当前 Revision 更新元数据或规格 |
| `05_delete_environment_resource.py` | `DeleteEnvironmentResource` | 提交删除并可选等待 `deleted` |

## 最新接口要点

- 网络请求使用公开 TOP JSON 契约：字段递归转换为 PascalCase。
- 响应从 `Result` 解包，并在脚本内部归一化为 snake_case。
- `EnvVars` 是用户字典，变量名原样保留。
- List 使用 `MaxResults`、`NextToken`，响应为 `Items`、`NextToken`。
- Create 必须包含 `Name`；脚本默认使用 `AGENTKIT_RESOURCE_NAME` 或
  `self-hosted-sandbox-http`。
- Update 必须包含最新 `ExpectedRevision` 和精确的 `UpdateMask`。
- Delete 只发送 `ResourceId` 和 `ClientToken`，不再发送 Revision；返回仅含
  `ResourceId`，进度通过 Get 查询。
- 资源响应不再包含 `Target`、`Spec`、`Components`、`LastOperation` 或
  `ResourceMode`。当前配置在 `Config`，失败原因在 `ErrorCode`。
- `ready` 只有在 `DesiredGeneration == ObservedGeneration` 且没有
  `ErrorCode` 时才视为完成；删除以 `deleted` 为完成状态。

## 安装

建议使用 `uv`，不在仓库中创建额外依赖文件：

```bash
uv venv
uv pip install -r requirements.txt
source .venv/bin/activate
```

## TOP 配置

Volcengine：

```bash
export VOLCENGINE_ACCESS_KEY='<access-key>'
export VOLCENGINE_SECRET_KEY='<secret-key>'
export VOLCENGINE_REGION='cn-beijing'
```

PPE：

```bash
export VOLCENGINE_AGENTKIT_HOST='open.volcengineapi.com'
export VOLCENGINE_AGENTKIT_SERVICE='agentkit_ppe'
```

BytePlus：

```bash
export AGENTKIT_CLOUD_PROVIDER='byteplus'
export BYTEPLUS_ACCESS_KEY='<access-key>'
export BYTEPLUS_SECRET_KEY='<secret-key>'
export BYTEPLUS_REGION='ap-southeast-1'
```

直连模式：

```bash
export MA_RESOURCE_BASE_URL='https://example.internal/environment-resources'
export MA_RESOURCE_API_KEY='<account-scoped-api-key>'
```

脚本不会自动加载 `.env`。需要时由 shell 注入：

```bash
set -a
source /path/to/.env
set +a
```

## Ark 目标配置

```bash
export AGENTKIT_ENVIRONMENT_ID='<environment-id>'
export AGENTKIT_ENVIRONMENT_BASE_URL='https://ark.cn-beijing.volces.com/api/v3'
export AGENTKIT_ENVIRONMENT_KEY='<runtime-secret>'
```

`AGENTKIT_ENVIRONMENT_KEY` 仅在 Create 和 Ark 规格 Update 请求中注入，不写入状态
文件。Ark Create 还需要 Runtime IAM Role。脚本可通过 `--role-name` 使用现有角色；
Volcengine TOP 未指定时会查找具备 `AgentKitDefaultRuntimeAccess` 的角色，必要时创建
并绑定策略。

## 创建

```bash
python 01_create_environment_resource.py \
  --name sandbox-http-demo \
  --description 'temporary verification resource' \
  --client-token create-001 \
  --wait
```

Ark 默认使用目录内定义的 Tool/Runtime `0.0.2` 镜像。可显式配置：

```bash
python 01_create_environment_resource.py \
  --sandbox-resources '{"cpu_milli":2000,"memory_mb":4096}' \
  --runtime-resources '{"cpu_milli":2000,"memory_mb":4096}' \
  --sandbox-env-vars '{"LOG_LEVEL":"info"}' \
  --wait
```

PPE 部署可能暂未接受 `Runtime.Resources`；这种环境可省略
`--runtime-resources`，客户端仍按最新契约支持该字段。

AgentKit 目标：

```bash
python 01_create_environment_resource.py \
  --target-type agentkit \
  --name agentkit-resource \
  --wait
```

AgentKit 模式不发送 Ark Base URL、Environment Key、Runtime 或 RoleName。只有显式
传入 Sandbox 字段时才发送 `Sandbox`，避免把客户端默认网络对象写入请求。

## 查询和分页

```bash
python 02_get_environment_resource.py
python 02_get_environment_resource.py --resource-id er_example --wait ready

python 03_list_environment_resources.py \
  --target-type ark \
  --environment-id "$AGENTKIT_ENVIRONMENT_ID" \
  --max-results 20 \
  --all

python 03_list_environment_resources.py --next-token '<previous-next-token>'
```

List 支持 `--target-type`、`--environment-id`、`--status`、
`--include-deleted`、`--max-results` 和 `--next-token`。List 不覆盖本地资源状态。

## 更新

Update 默认从 `.environment_resource_state.json` 读取 ResourceId 和最新 Revision：

```bash
python 04_update_environment_resource.py \
  --name sandbox-http-demo-v2 \
  --description 'updated metadata' \
  --wait

python 04_update_environment_resource.py \
  --sandbox-env-vars '{"LOG_LEVEL":"debug"}' \
  --wait

python 04_update_environment_resource.py \
  --runtime-resources '{"cpu_milli":4000,"memory_mb":8192}' \
  --role-name CustomerRuntimeRole \
  --wait
```

支持的字段为 `Name`、`Description`、`Sandbox.ImageUrl`、
`Sandbox.Resources`、`Sandbox.Networking`、`Sandbox.EnvVars`、
`Runtime.Resources` 和 `RoleName`。脚本自动生成 PascalCase `UpdateMask`。Ark
规格更新自动补交 Environment Key；纯元数据更新不发送密钥。

相同操作重试时必须复用原 `--client-token`、ResourceId、ExpectedRevision 和全部
请求参数。新操作应使用新 token，并先 Get 刷新 Revision。

## 删除

```bash
python 05_delete_environment_resource.py --client-token delete-001 --wait
python 02_get_environment_resource.py --wait deleted
```

Delete 不读取或发送 ExpectedRevision。未显式传 ResourceId 时只从环境变量
`AGENTKIT_RESOURCE_ID` 或本地状态文件读取 ID。

## 输出、状态和验证

- `--json` 输出脱敏后的完整事件；默认输出中文摘要。
- `--dry-run` 不访问网络、IAM 或状态文件。
- `AGENTKIT_RESOURCE_STATE` 可指定独立状态文件。状态只保存 ID、Revision、状态、
  代次、错误码及 endpoint，不保存请求、环境变量或密钥。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS` 默认 1200 秒；
  `AGENTKIT_POLL_INTERVAL_SECONDS` 默认 5 秒。

离线测试：

```bash
uv run --with 'requests>=2.31,<3' \
  python -m unittest discover -s tests -v
```

当前契约依据与 PPE 验证记录见
[`doc/environment_resource_contract.md`](doc/environment_resource_contract.md)。
