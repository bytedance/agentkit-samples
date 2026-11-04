# 火山引擎 RuntimeTemplate HTTP API 示例

使用 `--workspace-id <id>`、`HARNESS_INFRA_WORKSPACE_ID`（兼容
`AGENTKIT_WORKSPACE_ID`）或 YAML 顶层 `workspace_id`，按此顺序优先。
Create/Get/List 的请求发送 `WorkspaceId`，返回归属写回配置；
未指定时使用服务端唯一 ACTIVE DEFAULT。分页和轮询必须使用同一 Workspace，
跨 Workspace Get 返回不存在，NextToken 不能跨范围复用。
Update/Delete 按模板 ID 定位。云 ProjectName 由服务端根据 Workspace 解析。

新模板还必须通过 `--session-store-id`、`AGENTKIT_SESSION_STORE_ID` 或
`runtime_template.session_store_id` 引用已 Ready 的账号级 SessionStore。
该引用与 `DATABASE_POSTGRESQL_*` / `DATABASE_MYSQL_*` 环境变量互斥。

[BytePlus English](README_en.md)

本示例通过火山引擎 TOP HTTP 接口调用 RuntimeTemplate 完整生命周期，不依赖
AgentKit SDK：

1. `CreateRuntimeTemplate`
2. `GetRuntimeTemplate`
3. `ListRuntimeTemplates`
4. `UpdateRuntimeTemplate`
5. `DeleteRuntimeTemplate`

请求使用 API Version `2025-10-30`，发送至
`https://open.volcengineapi.com`。接口字段和边界来自 `akx` 仓库
`origin/master:docs/harness-infra/api/runtime-template-api.md`。

## 1. 安装依赖

```bash
cd python/01-tutorials/01-agentkit-runtime/runtime_template_http
uv venv --allow-existing
uv pip install -r requirements.txt \
  --index-url https://mirrors.aliyun.com/pypi/simple/
source .venv/bin/activate
```

## 2. 创建配置文件

```bash
cp -n config.yaml.example config.yaml
chmod 600 config.yaml
```

填写 `config.yaml` 中的火山引擎 AK/SK、Region 和 `runtime_template` 创建规格。
脚本默认从自身目录读取配置，不受启动目录影响；也可使用 `--config <path>`
或 `AGENTKIT_RUNTIME_TEMPLATE_CONFIG` 指定其他文件。

`runtime_template.name_prefix` 会自动追加 UTC 时间和随机后缀，避免复用已删除的
模板名称。CLI 参数可显式覆盖对应 YAML 字段。

配置中的 `role_name` 为空时，示例会复用账号中的
`AgentKitDefaultRuntimeAccess` 角色；角色不存在时自动创建，并附加同名系统
策略。显式角色必须已存在，示例不会修改其信任策略或权限。临时凭据仍通过
`VOLCENGINE_AGENTKIT_SESSION_TOKEN` 提供。

## 3. 预览创建请求

`--dry-run` 不读取凭据、不访问网络，也不更新配置中的运行时状态：

```bash
python 01_create_runtime_template.py --dry-run --json
```

## 4. 创建并等待 Ready

```bash
python 01_create_runtime_template.py --wait
```

`image_url: null` 且 `runtime: {}` 时使用服务端默认镜像、端口和启动命令。
只有镜像真实存在且当前账号可拉取时才配置 `image_url`。

`Envs` 会由服务明文保存并在查询响应中返回，只能放普通配置，禁止写入 API
Key、Token 或密码。

创建成功后，脚本会将模板 ID、状态和 Endpoint 写入 `config.yaml` 的
`runtime_template.id/status/endpoint`，后续命令自动读取，无需设置本地状态路径。

## 5. 查询和分页

```bash
python 02_get_runtime_template.py
python 03_list_runtime_templates.py --max-results 1 --all
```

只查询单页时，响应中的 `NextToken` 可继续传给
`--next-token '<previous-next-token>'`。

## 6. 更新 Description 和 Meta

```bash
python 04_update_runtime_template.py \
  --description '更新后的描述' \
  --meta '{"purpose":"review"}' \
  --wait
```

本接口创建并管理关联 Runtime，因此只允许更新 `Description` 和 `Meta`。
`Resources`、`ImageUrl`、`Runtime`、`Name`、`RoleName` 和 `Envs` 不能原地
更新；需要修改这些字段时应创建替代模板。

清空描述和元数据可执行：

```bash
python 04_update_runtime_template.py \
  --clear-description \
  --clear-meta
```

## 7. 删除并验证

删除前必须清理引用该模板的活动 Session 和 Environment：

```bash
python 05_delete_runtime_template.py \
  --reason '教程资源清理' \
  --wait
```

`--wait` 会持续调用 Get，直到服务返回 `404 ResourceNotFound`；确认删除后，
脚本自动清空 `config.yaml` 中的 `id/status/endpoint`。

## 幂等重试

Create、Update、Delete 会使用 `ClientToken`。请求结果不明确时，必须复用原
token 和完全相同的请求参数；新操作必须使用新 token。

## 状态、安全和测试

运行时只将 Endpoint、RuntimeTemplateId 和 Status 写回 `config.yaml`，不保存
响应中的 `Envs` 或完整请求体，配置权限固定为 `0600`。可用
`AGENTKIT_RUNTIME_TEMPLATE_ID` 或 `--runtime-template-id` 显式选择模板。

```bash
uv run --with-requirements requirements.txt \
  python -m unittest discover -s tests -v
```

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `AGENTKIT_RUNTIME_TEMPLATE_CONFIG` | `./config.yaml` | YAML 配置路径 |
| `AGENTKIT_HTTP_TIMEOUT_SECONDS` | `30` | 单次 HTTP 超时 |
| `AGENTKIT_HTTP_ATTEMPTS` | `3` | 网络错误、429、503 最大尝试次数 |
| `AGENTKIT_POLL_INTERVAL_SECONDS` | `5` | 轮询间隔 |
| `AGENTKIT_POLL_TIMEOUT_SECONDS` | `900` | 轮询总超时 |

详细契约见 [doc/runtime_template_contract.md](doc/runtime_template_contract.md)。
