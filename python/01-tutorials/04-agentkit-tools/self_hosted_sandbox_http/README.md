# Self-hosted Sandbox：EnvironmentResource HTTP 示例

[English](README_en.md)

通过 HTTP 演示 `EnvironmentResource` 资源组的创建、查询、列表、更新和删除。资源组管理 Sandbox Tool 及可选的 ACTB dispatcher Runtime；已有 Environment 的 ID 作为输入。依赖仅为 `requests`，无需 AgentKit SDK。

| 脚本 | Action | 用途 |
| --- | --- | --- |
| `01_create_environment_resource.py` | `CreateEnvironmentResource` | 提交创建，可用 `--wait` 等待就绪 |
| `02_get_environment_resource.py` | `GetEnvironmentResource` | 查询状态、revision、组件；可继续轮询 |
| `03_list_environment_resources.py` | `ListEnvironmentResources` | 筛选、单页查询或 `--all` 遍历分页 |
| `04_update_environment_resource.py` | `UpdateEnvironmentResource` | 更新元数据或 Sandbox 规格，自动生成 `update_mask` |
| `05_delete_environment_resource.py` | `DeleteEnvironmentResource` | 删除所属组件，可等待 `deleted` 墓碑 |

## 1. 安装与入口

Python 3.10+，在本目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**默认走 TOP OpenAPI，使用 AK/SK 签名。** 目标平台须已注册并发布上述五个 Action；服务端存在接口不代表所有区域或平台均已发布。

```bash
export AGENTKIT_CLOUD_PROVIDER=volcengine
export VOLCENGINE_ACCESS_KEY='<your-access-key>'
export VOLCENGINE_SECRET_KEY='<your-secret-key>'
export VOLCENGINE_AGENTKIT_REGION=cn-beijing
# 如使用已发布这些 Action 的自定义入口：
# export VOLCENGINE_AGENTKIT_HOST='<openapi-host-without-scheme>'
# export VOLCENGINE_AGENTKIT_SERVICE=agentkit
```

默认请求为 `POST https://open.volcengineapi.com/?Action=<Action>&Version=2025-10-30`。请求 JSON 字段保持下文的 `snake_case`；成功响应兼容顶层资源对象 / `data` 列表，以及 `Result` 包装；签名入口不决定响应是否包装。

若目标部署提供直连路由及账号级 API Key，可显式选择直连 HTTP：

```bash
export MA_RESOURCE_BASE_URL='https://<your-ma-infra-endpoint>'
export MA_RESOURCE_API_KEY='<account-scoped-api-key>'
```

设置 `MA_RESOURCE_BASE_URL` 后优先直连：`POST <base-url>/<Action>`，用 `x-api-key` 认证，直接读取 JSON 响应，不使用 AK/SK 或 `Result` 包装。请使用该部署实际开放的入口和认证方式；示例不会自行添加网关可信账号头。切回 TOP 时 `unset MA_RESOURCE_BASE_URL MA_RESOURCE_API_KEY`。

BytePlus 保留相同签名配置方式（这些 Action 在目标平台的可用性需单独确认）：

```bash
export AGENTKIT_CLOUD_PROVIDER=byteplus
export BYTEPLUS_ACCESS_KEY='<your-access-key>'
export BYTEPLUS_SECRET_KEY='<your-secret-key>'
export BYTEPLUS_AGENTKIT_REGION=ap-southeast-1
# 默认 host: agentkit.ap-southeast-1.byteplusapi.com
# export BYTEPLUS_AGENTKIT_HOST='<published-openapi-host>'
```

临时凭据可分别使用 `VOLCENGINE_SESSION_TOKEN` / `BYTEPLUS_SESSION_TOKEN`。自定义签名服务名及版本用 `VOLCENGINE_AGENTKIT_SERVICE`、`VOLCENGINE_AGENTKIT_API_VERSION`（BytePlus 使用同名 `BYTEPLUS_` 前缀）。

## 2. 创建 self-host 资源组

默认采用 `target.type=ark`：向已有外部 Environment 配套创建 Sandbox Tool 与 ACTB dispatcher Runtime。

| 参数 | Ark 默认值 |
| --- | --- |
| `--target-type` | `ark`（可由 `AGENTKIT_RESOURCE_TARGET` 覆盖） |
| `--sandbox-image` | `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:tool-ark-skills-0.0.2` |
| `--runtime-image` | `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:runtime-ark-skills-0.0.2` |

配置下面必需的 Environment 信息和前文认证后，直接运行 `python 01_create_environment_resource.py` 即可。所有创建命令行参数均为可选；`--client-token` 省略时自动生成并打印，name、description、region、env_vars、Skill Space 未配置时不发送。

```bash
export AGENTKIT_RESOURCE_TARGET=ark
export AGENTKIT_ENVIRONMENT_ID='<existing-environment-id>'
export AGENTKIT_ENVIRONMENT_BASE_URL='https://<external-environment-api>'
export AGENTKIT_ENVIRONMENT_KEY='<environment-data-plane-key>'
# 可选：需要挂载且属于当前账号的 Skill Space
# export AGENTKIT_SKILL_SPACE_ID='<skill-space-id>'

# 可在未配置凭据时预览请求；--json 查看完整的脱敏请求体
python 01_create_environment_resource.py --dry-run --json

# 提交创建并等待；去掉 --wait 可在收到受理响应后退出
python 01_create_environment_resource.py --wait
```

请求体结构如下，`target.environment_key` 与控制面 AK/SK、账号级 API Key 是不同凭据：

```json
{
  "client_token": "<automatically-generated-token>",
  "resource_mode": "runtime_and_sandbox",
  "target": {
    "type": "ark",
    "environment_id": "env_example",
    "base_url": "https://external.example.com",
    "environment_key": "<environment-data-plane-key>"
  },
  "sandbox": {
    "profile": "ark_skills",
    "image_url": "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:tool-ark-skills-0.0.2"
  },
  "runtime": {"image_url": "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:runtime-ark-skills-0.0.2"}
}
```

`--sandbox-image`、`--runtime-image` 可覆盖上述 Ark 默认镜像；显式传空字符串时省略对应镜像字段，使用服务端默认值。AgentKit 模式省略 Sandbox 镜像时仍使用服务端默认值，且不发送 Runtime。Runtime 镜像应为 ACTB self-host dispatcher。自定义 Tool 环境变量使用 `--sandbox-env-vars '{"APP_MODE":"demo"}'` 或 `--sandbox-env-vars @env-vars.json`；所有值必须是字符串。`--skill-space-id` 会写入 `sandbox.env_vars.SKILL_SPACE_ID`。新式资源组不接受 packages 或 RuntimeTemplate 参数。

仅创建 AgentKit Sandbox 的另一种模式：

```bash
export AGENTKIT_RESOURCE_TARGET=agentkit
export AGENTKIT_ENVIRONMENT_ID='<existing-agentkit-cloud-environment-id>'
python 01_create_environment_resource.py --wait
```

该模式发送 `resource_mode=sandbox_only`、`sandbox.profile=ma_infra`，省略 `runtime` 和外部 Environment Key。目标必须是当前账号未归档的 cloud Environment，账号 Endpoint 已就绪，且没有活动资源组或绑定。普通 cloud Environment 创建流程可能已自动创建资源组，应先 List 查询。

## 3. 查询和列表

```bash
# 使用最近一次 Create/Get/Update/Delete 保存的 resource_id
python 02_get_environment_resource.py
python 02_get_environment_resource.py --wait ready

# 任意已知资源可单独查询
python 02_get_environment_resource.py --resource-id er_example

# 无参数时发送 {}，使用服务端默认分页
python 03_list_environment_resources.py
python 03_list_environment_resources.py --target-type ark --limit 20 --all
python 03_list_environment_resources.py --environment-id "$AGENTKIT_ENVIRONMENT_ID" --include-deleted
python 03_list_environment_resources.py --target-type ark --page '<previous-next_page>'
```

List 的筛选参数包括 `--target-type`、`--environment-id`、`--resource-mode`、`--status`、`--include-deleted`。`--limit` 为 1～100。`--all` 逐页打印，跟随 `next_page`；手动续页时保持账号和筛选条件一致。List 不修改当前资源的本地状态。

## 4. 更新

更新默认从 `.environment_resource_state.json` 读取 `resource_id` 和 `revision`，后者作为 API 的 `expected_revision`；无需手填 ID 或版本。Create/Get/Update/Delete 收到资源响应后都会刷新该文件。需要同步云端最新版本时先运行 Get。

```bash
python 02_get_environment_resource.py
python 04_update_environment_resource.py \
  --name 'renamed-sandbox' --description 'HTTP example' --wait

# 使用前一次操作写回 JSON 的 revision 提交规格更新
python 04_update_environment_resource.py \
  --sandbox-image 'registry.example.com/sandbox:v2' \
  --sandbox-env-vars '{"APP_MODE":"updated"}' --wait
```

第二条更新中的镜像应替换为可拉取的真实镜像。仅名称/描述更新同步完成；Sandbox 规格更新进入 `updating`，后台替换组件。Ark 规格更新必须重新提供 `AGENTKIT_ENVIRONMENT_KEY`，脚本仅在该场景注入 `target.environment_key`。AgentKit 规格更新使用 `--target-type agentkit` 或前文的 `AGENTKIT_RESOURCE_TARGET=agentkit`。

| 参数 | `update_mask` 路径 | 语义 |
| --- | --- | --- |
| `--name` | `name` | 修改名称 |
| `--description` / `--clear-description` | `description` | 设置描述 / 发送 `null` 清空 |
| `--sandbox-image` | `sandbox.image_url` | 更换 Sandbox 镜像 |
| `--sandbox-env-vars` | `sandbox.env_vars` | 替换自定义环境变量；`'{}'` 清空，包含 Skill Space 配置 |
| `--sandbox-resources` | `sandbox.resources` | JSON 对象或 `@file.json` |
| `--sandbox-networking` | `sandbox.networking` | JSON 对象或 `@file.json`，仍受既有环境策略约束 |

值放在原字段位置，示例：`{"update_mask":["sandbox.env_vars"],"sandbox":{"env_vars":{}}}`。目标、区域、模式和 profile 不可更新。

## 5. 删除

完成外部 Environment 的业务 drain，并确认资源不再被使用后，可先 Get 刷新本地 JSON，再直接删除。删除脚本自动读取其中的 ID 和 revision：

```bash
python 02_get_environment_resource.py
python 05_delete_environment_resource.py --wait

# 删除后仍可查询墓碑
python 02_get_environment_resource.py --wait deleted
python 03_list_environment_resources.py --include-deleted --all
```

删除先清理本接口拥有的 Runtime，再清理 Tool；`ownership=referenced` 的历史引用组件不被销毁，目标 Environment 不被删除。本地资源存在未终止 Session、未完成 Work 或 Sandbox 创建意图时，会返回 `ResourceInUse`。

## 输出示例

创建请求刚被受理时，输出类似下面的摘要（ID 为示例）：

```text
[已受理] 创建请求已提交，尚未确认操作完成。
资源 ID: er_example
当前状态: 创建中 (creating)
当前版本 (revision): 1
状态已保存: .../.environment_resource_state.json
继续等待: python 02_get_environment_resource.py --resource-id er_example --wait ready
```

使用 `--wait` 后，确认完成会显示 `[成功] 环境资源创建成功。`；失败则显示 `[失败]` 和 `失败原因`，不会把 HTTP 200 当作创建成功。需要组件历史等完整详情时：

```bash
python 02_get_environment_resource.py --json
```

## 状态、重试和配置

- 默认输出中文摘要：请求进度、是否受理/成功/失败、资源 ID、状态、revision、可用的 Tool/Runtime ID 和状态文件位置；失败时直接显示错误码。只有确认操作完成才显示“成功”，异步提交先显示“已受理”。List 按行展示资源，并提示数量及后续页。
- 所有脚本支持 `--json`，切换为完整脱敏 JSON 事件（`request`、`response`、`poll`、`completed`，List 为 `page`）；默认摘要不会混入该输出，便于程序解析。`--dry-run` 只预览，不访问网络或写状态。
- 创建或规格更新等待 `ready` 时，同时检查 `last_operation.status=completed` 和 `desired_generation=observed_generation`；纯元数据操作只要求资源 `ready` 且该操作完成，不要求更新代次。更新回滚的 `ready + failed_clean` 会报错。等待删除以 `deleted` 且操作完成为准。失败时检查 `last_operation` 与 `components.history`。
- 创建、更新、删除的 `--client-token` 均可选，省略时自动生成并打印本次操作的 token。**同一次请求超时重试，使用 `--client-token <上次打印的token>`，保持 token、resource_id、expected_revision 和所有请求参数不变。** HTTP 自动重试复用原 token 和请求体，不自动刷新版本；手动重试若本地 JSON 已变化，应同时显式指定原 `--resource-id` 和 `--expected-revision`。重新运行创建、更新或删除脚本且省略 token 则视为新操作。`RevisionConflict` 时先 Get，再决定是否用新 token 提交新操作。
- Ark 创建/规格更新的 Environment Key 仅供当前请求及服务端当前进程内的操作使用。服务端进程重启后，未完成操作可用相同 token、原参数及原 Key 重试恢复；单纯 Get 不会重新提交 Key。
- 轮询超时不会取消云端操作；可运行 `02_get_environment_resource.py --wait ready` 或 `--wait deleted` 继续查询。`delete_failed` 修复外部问题后，用最新 revision 和新 token 发起新删除。

| 环境变量 | 默认值 / 用途 |
| --- | --- |
| `AGENTKIT_RESOURCE_ID` | 手动选择资源；优先级低于 `--resource-id`，高于状态文件 |
| `AGENTKIT_RESOURCE_STATE` | 本目录 `.environment_resource_state.json`；只存 ID、revision、状态、代次及入口，不存密钥、请求或 env_vars |
| `AGENTKIT_RESOURCE_TARGET` | Create/Update 默认 `ark`，可设为 `agentkit`；List 默认查询所有目标 |
| `AGENTKIT_WAIT_TIMEOUT_SECONDS` | 1200 秒 |
| `AGENTKIT_POLL_INTERVAL_SECONDS` | 5 秒 |
| `AGENTKIT_HTTP_TIMEOUT_SECONDS` | 单次 HTTP 请求 30 秒 |
| `AGENTKIT_HTTP_RETRIES` | 连接失败及 HTTP 429/503 最多重试 2 次，保持请求体不变 |

参数优先级：ID 为 `--resource-id` → `AGENTKIT_RESOURCE_ID` → JSON；版本为 `--expected-revision` → JSON 中的 `revision`（不是 `runtime_version`）。如显式选择的 ID 与 JSON 不同，不会复用 JSON 的版本；先 Get 对应资源，或显式传入版本。状态文件缺失、版本非法或所属入口不符时会在发请求前报错。可通过 `AGENTKIT_RESOURCE_STATE=/path/to/resource.json` 选择其他状态文件。切换账号或演示多个资源时，使用不同状态文件，或同时显式提供 ID 和版本。输出会脱敏 Environment Key、凭据及 `env_vars` 的值。每个脚本均支持 `--help`。

## 本地验证

```bash
python -m unittest discover -s tests -v
```

测试使用本机模拟 HTTP 服务验证请求路径、签名头、响应解包、幂等重试参数、分页、异步终态及脱敏；不访问真实云服务。2026-09-24 已使用真实 Volcengine TOP 的 List/Get 只读确认无 `Result` 包装的响应，并验证修复后的 Get 解析；这不代表资源创建成功，尚未验证完整云生命周期或 BytePlus。接口取证与验证边界见 [接口核对记录](doc/environment_resource_contract.md)。

## 排障：响应解析与异步失败

若旧版脚本报 `TOP response is missing a JSON object Result`，请求可能已受理。当前解析已兼容 TOP 直接透传的资源 JSON。先通过 `03_list_environment_resources.py --environment-id <environment-id>` 找到资源，再用 `02_get_environment_resource.py --resource-id <resource-id>` 查询，避免省略 token 直接创建新操作。未知响应仍报错并显示顶层字段名，不将任意 HTTP 200 对象认定为成功。

若资源本身是 `failed`，查看 `last_operation.error_code` 与 `components.history`。例如 `Provider.InvalidParameter.RoleName` 是下游创建组件时拒绝 RoleName，独立于本地 JSON 解析。Ark Tool 的 RoleName 来源为服务端 `MA_RUNTIME_ROLE_NAME`；需核对实际部署值及目标账号角色，不能通过添加未声明的创建请求字段修复。
