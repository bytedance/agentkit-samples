# VKE Runtime Manager

这个示例用于通过 AgentKit OpenAPI 创建 VKE Runtime，并查询 Runtime 状态。

脚本提供四个常用命令：

- `create`：创建 Runtime，或复用本地 state 中已有的 RuntimeId。随后按间隔查询状态，直到 Runtime 变为 `Ready`、进入失败状态，或等待超时。
- `get`：查询已有 Runtime 状态。默认读取本地 state 文件里的 `RuntimeId`，也可以通过 `--runtime-id` 手动传入。
- `update`：更新已有 Runtime 的镜像地址。默认读取本地 state 文件里的 `RuntimeId`，更新后继续轮询状态。
- `delete`：删除已有 Runtime。默认读取本地 state 文件里的 `RuntimeId`，删除后会更新 state。

终端只展示关键节点和状态摘要；完整 OpenAPI 请求、响应、HTTP 状态码和 `RequestId` 会写入日志文件。

## 准备配置

复制示例配置：

```bash
cp config.example.json config.json
```

编辑 `config.json`，至少填写这些字段。

凭证字段请只在本地 `config.json` 中填写，不要提交到代码仓库：

- `volcengine_access_key`
- `volcengine_secret_key`

最小配置示例：

```json
{
  "volcengine_access_key": "YOUR_AK",
  "volcengine_secret_key": "YOUR_SK",
  "volcengine_region": "cn-beijing",
  "volcengine_agentkit_host": "agentkit-stg.cn-beijing.volcengineapi.com",
  "volcengine_agentkit_api_version": "2025-10-30",
  "volcengine_agentkit_service": "agentkit_stg",
  "x_forward_env": "",
  "name": "sch-hia1",
  "artifact_url": "YOUR_IMAGE_URL",
  "role_name": "YOUR_RUNTIME_ROLE_NAME",
  "DiscoveryUrl": "YOUR_OIDC_DISCOVERY_URL",
  "namespace": "YOUR_VKE_NAMESPACE",
  "vke_cluster_id": "YOUR_VKE_CLUSTER_ID",
  "workspace_id": "default",
  "min_instance": 1,
  "max_instance": 2,
  "Envs": [
    {
      "Key": "LOG_LEVEL",
      "Value": "info"
    }
  ]
}
```

字段说明：

| 字段 | 是否必填 | 说明 |
| --- | --- | --- |
| `volcengine_access_key` | 是 | 火山引擎 AK。 |
| `volcengine_secret_key` | 是 | 火山引擎 SK。 |
| `volcengine_region` | 是 | AgentKit 服务地域，例如 `cn-beijing`。 |
| `volcengine_agentkit_host` | 是 | AgentKit 服务域名，例如 `agentkit.cn-beijing.volcengineapi.com`。 |
| `volcengine_agentkit_api_version` | 是 | AgentKit OpenAPI 版本。 |
| `volcengine_agentkit_service` | 是 | AgentKit 服务名称，线上环境通常为 `agentkit`。 |
| `x_forward_env` | 否 | 测试环境标识；为空时不会放入请求 header。 |
| `name` | 是 | Runtime 名称前缀；也兼容 `runtime_name`、`runtimename`。 |
| `artifact_url` | 是 | Runtime 镜像地址。 |
| `role_name` | 是 | 火山引擎 IAM Role 名称。 |
| `DiscoveryUrl` | 是 | OAuth/OIDC IdP discovery URL。 |
| `namespace` | 是 | VKE 集群 namespace。 |
| `vke_cluster_id` | 是 | VKE 集群 ID。 |
| `workspace_id` | 否 | CP 服务工作区，未配置或为空时默认为 `default`。 |
| `min_instance` | 否 | AgentKit Runtime 最小实例数，默认 `1`。 |
| `max_instance` | 否 | AgentKit Runtime 最大实例数，默认 `2`。 |
| `Envs` | 否 | Runtime 环境变量数组，会作为 CreateRuntime 顶层 `Envs` 字段传入。 |

`name` 是 Runtime 名称前缀。创建时脚本会自动拼接时间戳，最终名称格式为：

```text
<name>-YYYYmmddHHMMSS
```

## 配置 Runtime 环境变量

如果需要给 Runtime 注入环境变量，可以在 `config.json` 顶层配置 `Envs`：

```json
{
  "Envs": [
    {
      "Key": "HI_AGENT_CONFIG_FILE",
      "Value": "generalAgent_v3.zip"
    },
    {
      "Key": "LOG_LEVEL",
      "Value": "info"
    }
  ]
}
```

脚本根据平铺配置自动构造 CreateRuntime body 时，会把 `Envs` 原样添加到最外层：

```json
{
  "name": "sch-hia1-YYYYmmddHHMMSS",
  "artifact_type": "image",
  "artifact_url": "YOUR_IMAGE_URL",
  "role_name": "YOUR_RUNTIME_ROLE_NAME",
  "provider": "VKE",
  "Envs": [
    {
      "Key": "HI_AGENT_CONFIG_FILE",
      "Value": "generalAgent_v3.zip"
    }
  ]
}
```

`Envs` 必须是数组，每个元素必须是包含 `Key` 和 `Value` 的对象；`Key` 需要是非空字符串，`Value` 需要是字符串。数据库密码、Redis 密码等敏感环境变量请只写在本地 `config.json`，不要提交到代码仓库。

## 安装依赖

如果使用 `uv`：

```bash
uv sync
```

然后用 `uv run` 执行脚本：

```bash
uv run python create_vke_runtime.py get --config config.json
```

如果只想临时带上依赖运行：

```bash
uv run --with requests python create_vke_runtime.py get --config config.json
```

也可以使用 `pip`：

```bash
pip install -r requirements.txt
```

## 查看帮助

```bash
python3 create_vke_runtime.py -h
python3 create_vke_runtime.py create -h
python3 create_vke_runtime.py get -h
python3 create_vke_runtime.py update -h
python3 create_vke_runtime.py delete -h
```

通用参数：

| 参数 | 说明 |
| --- | --- |
| `--config CONFIG` | 必填，配置文件路径。 |
| `--state STATE` | Runtime state JSON 路径。`create` 默认先复用最新且包含 `RuntimeId` 的 state 防重放；没有可复用 state 时才生成 `<config>.YYYYmmddHHMMSS.vke-runtime-state.json`。`get`、`update`、`delete` 默认读取最新的匹配 state 文件。 |
| `--log LOG` | API 详细日志路径。默认是 `<state>.log`。 |
| `--quiet` | 隐藏非必要终端提示；状态摘要仍会输出。 |

## 创建 Runtime

```bash
python3 create_vke_runtime.py create --config config.json
```

创建流程：

1. 读取并校验 `config.json`。
2. 如果没有传 `--state`，读取当前 `config.json` 对应的最新 state 文件；如果 state 中已有 `runtime_id`，跳过 `CreateRuntime`，直接查询已有 Runtime 状态，避免重复创建。
3. 如果传了 `--state`，读取指定 state；如果里面已有 `runtime_id`，同样跳过创建。
4. 如果没有可复用的 `runtime_id`，生成新的带时间戳 state 文件、构造 CreateRuntime body，并给 Runtime 名称追加时间戳。
5. 创建 `<state>.lock`，避免并发重复创建。
6. 调用 `CreateRuntime`，把 RuntimeId、状态、元信息写入 state 文件。
7. 按 `--interval` 轮询 `GetRuntime`，最多等待 `--timeout` 秒。

新建时默认 state 文件：

```bash
config.json.20260729170112.vke-runtime-state.json
```

注意：上面的文件只会在没有可复用 state 时创建。如果已存在最新 state 且里面有 `runtime_id`，脚本会复用它并跳过创建，控制台会提示：

```text
== CreateRuntime ==
Status: Skipped
RuntimeId: r-xxxx
State: config.json.20260729170112.vke-runtime-state.json
Reason: RuntimeId found in state; skip create to avoid replay
Next: Use get/update/delete, or pass --state NEW_STATE to create a new runtime
```

默认日志文件：

```bash
config.json.20260729170112.vke-runtime-state.json.log
```

时间戳为创建时刻，格式为 `YYYYmmddHHMMSS`。如果同一秒内生成的文件已存在，脚本会追加 `.1`、`.2` 这样的序号。如果不传 `--state`，后续 `get`、`update`、`delete` 会自动读取当前 `config.json` 对应的最新 state 文件。

如果你确认要新建一个 Runtime，而不是复用最新 state，请显式指定一个新的 state 路径：

```bash
python3 create_vke_runtime.py create --config config.json --state config.json.20260729173000.vke-runtime-state.json
```

手动指定 state 和日志路径：

```bash
python3 create_vke_runtime.py create --config config.json --state runtime-state.json --log runtime.log
```

调整轮询时间：

```bash
python3 create_vke_runtime.py create --config config.json --timeout 600 --interval 15
```

如果 Runtime 状态变为 `Ready`，脚本结束。若状态进入 `Failed`、`CreateFailed` 或 `Error`，脚本会报错退出。若超时仍未 `Ready`，脚本会提示稍后用 `get` 命令继续查询。

`CreateRuntime` 成功后会在控制台打印 `RequestId`，同时完整请求和响应会写入日志文件。

## 查询 Runtime

使用 state 文件里的 `RuntimeId`：

```bash
python3 create_vke_runtime.py get --config config.json
```

手动指定 `RuntimeId`：

```bash
python3 create_vke_runtime.py get --config config.json --runtime-id r-xxxx
```

查询成功后，脚本会更新 state 文件中的：

- `runtime_id`
- `status`
- `endpoint`
- `updated_at`
- `last_get_response_metadata`

如果查询 Runtime 状态失败，终端会展示友好提示，并带上 `request_id`，例如：

```text
查看 runtime 状态失败，请反馈~ request_id: req-xxxx，错误信息: Code - Message
```

## 更新 Runtime

使用 state 文件里的 `RuntimeId`，并指定新的镜像地址：

```bash
python3 create_vke_runtime.py update --config config.json --artifact-url IMAGE_URL
```

手动指定 `RuntimeId`：

```bash
python3 create_vke_runtime.py update --config config.json --runtime-id r-xxxx --artifact-url IMAGE_URL
```

更新请求 body 会被构造成：

```json
{
  "RuntimeId": "r-xxxx",
  "ArtifactUrl": "IMAGE_URL"
}
```

更新成功后，脚本会先把 state 标记为 `Updating`，再按 `--interval` 轮询 `GetRuntime`，最多等待 `--timeout` 秒：

```bash
python3 create_vke_runtime.py update --config config.json --artifact-url IMAGE_URL --timeout 600 --interval 15
```

`UpdateRuntime` 成功后会在控制台打印 `RequestId`，同时完整请求和响应会写入日志文件。

也可以使用完整 UpdateRuntime body：

```bash
python3 create_vke_runtime.py update --config config.json --body-file update-body.json
```

`update-body.json` 必须是合法 JSON，并包含：

- `RuntimeId`
- `ArtifactUrl`

示例：

```json
{
  "RuntimeId": "r-xxxx",
  "ArtifactUrl": "agentkit-cli-2107625663-cn-beijing.cr.volces.com/agentkit/simple_agent:20260306115003"
}
```

如果更新失败，终端会展示友好提示，并带上 `request_id`：

```text
更新 runtime 失败，请反馈~ request_id: req-xxxx，错误信息: Code - Message
```

## 删除 Runtime

使用 state 文件里的 `RuntimeId`：

```bash
python3 create_vke_runtime.py delete --config config.json
```

手动指定 `RuntimeId`：

```bash
python3 create_vke_runtime.py delete --config config.json --runtime-id r-xxxx
```

删除请求 body 会被构造成：

```json
{
  "RuntimeId": "r-xxxx"
}
```

删除成功后，脚本会把 state 标记为 `Deleted`，把删除过的 ID 写入 `deleted_runtime_id`，并清空当前活跃的 `runtime_id`。这样后续再执行 `create` 时，不会被已删除的旧 RuntimeId 阻止重新创建。

`DeleteRuntime` 成功后会在控制台打印 `RequestId`，同时完整请求和响应会写入日志文件。

如果删除失败，终端会展示友好提示，并带上 `request_id`：

```text
删除 runtime 失败，请反馈~ request_id: req-xxxx，错误信息: Code - Message
```

## 终端输出和日志

终端默认只展示关键节点，例如：

```text
Log: config.json.20260729170112.vke-runtime-state.json.log

== GetRuntime ==
RuntimeId: r-xxxx

== Runtime Status ==
RuntimeId: r-xxxx
Status: Ready
Endpoint: https://example.runtime
RequestId: req-xxxx
State: config.json.20260729170112.vke-runtime-state.json
```

创建、更新、删除成功时也会打印对应接口的 `RequestId`：

```text
== CreateRuntime ==
Status: Succeeded
RuntimeId: r-xxxx
RequestId: req-create-xxxx

== UpdateRuntime ==
Status: Succeeded
RuntimeId: r-xxxx
RequestId: req-update-xxxx

== DeleteRuntime ==
Status: Succeeded
RuntimeId: r-xxxx
RequestId: req-delete-xxxx
```

详细 OpenAPI 请求和响应会追加写入日志文件。日志中包含：

- 请求 action、method、url、region、service、version
- 请求 headers 和 body
- 响应 HTTP 状态码和响应 body
- `RequestId`
- 错误摘要

日志里的 `Authorization` header 会被脱敏为 `<redacted>`。

## 使用完整 Body

脚本支持三种 CreateRuntime body 来源，优先级从高到低：

1. `--body-file body.json`
2. `config.json` 中的 `body` 字段
3. 根据 `config.json` 的平铺字段自动构造

使用 body 文件：

```bash
python3 create_vke_runtime.py create --config config.json --body-file body.json
```

传入完整 body 时，脚本会直接使用该 body，不再根据 `artifact_url`、`role_name`、`DiscoveryUrl`、`namespace`、`vke_cluster_id` 自动构造。body 中的 `name` 同样作为 Runtime 名称前缀，创建时会统一拼接时间戳。

完整 body 文件必须是合法 JSON，不支持 Python 注释。必填字段为：

- `name`
- `artifact_url`
- `role_name`
- `authorizer_configuration.CustomJwtAuthorizer.DiscoveryUrl`
- `provider_config.vke_configuration.vke_cluster_id`
- `provider_config.vke_configuration.namespace`

`min_instance`、`max_instance`、`Envs`、`provider_config.vke_configuration.workspace_id`、`provider_config.vke_configuration.nas_mount_configs` 为选填字段。

示例 `body.json`：

```json
{
  "name": "sch-hia1",
  "artifact_type": "image",
  "artifact_url": "agentkit-platform-2107625663-cn-beijing.cr.volces.com/hia/echo-api:2026-07-27",
  "role_name": "Agentkit_runtime_vke_test",
  "provider": "VKE",
  "min_instance": 1,
  "max_instance": 1,
  "Envs": [
    {
      "Key": "LOG_LEVEL",
      "Value": "info"
    }
  ],
  "authorizer_configuration": {
    "CustomJwtAuthorizer": {
      "DiscoveryUrl": "https://userpool-a95b65a4-5396-417a-a40f-79b266db0108.userpool.auth.id.cn-beijing.volces.com/.well-known/openid-configuration"
    }
  },
  "provider_config": {
    "vke_configuration": {
      "vke_cluster_id": "cd59nk5v1a4b3d2hchpmg",
      "namespace": "hiagent",
      "workspace_id": "YOUR_WORKSPACE_ID",
      "nas_mount_configs": [
        {
          "type": "NAS",
          "mount_path": "/mnt",
          "nas_config": {
            "type": "Extreme",
            "region": "cn-beijing",
            "subpath": "/",
            "filesystem_id": "enas-cnbja045e01672cd0a",
            "mount_point_id": "mount-1b8e7d05",
            "filesystem_name": "liulei-test",
            "mount_point_domain": "cnbja045e01672cd0a.vpc-mjim3l8hsem85smt1a0iylbv.nas.ivolces.com"
          }
        }
      ]
    }
  }
}
```

也可以把完整 body 放进 `config.json`：

```json
{
  "volcengine_access_key": "YOUR_AK",
  "volcengine_secret_key": "YOUR_SK",
  "volcengine_region": "cn-beijing",
  "volcengine_agentkit_host": "agentkit-stg.cn-beijing.volcengineapi.com",
  "volcengine_agentkit_api_version": "2025-10-30",
  "volcengine_agentkit_service": "agentkit_stg",
  "body": {
    "name": "sch-hia1",
    "artifact_type": "image",
    "artifact_url": "YOUR_IMAGE_URL",
    "role_name": "YOUR_RUNTIME_ROLE_NAME",
    "provider": "VKE",
    "authorizer_configuration": {
      "CustomJwtAuthorizer": {
        "DiscoveryUrl": "YOUR_OIDC_DISCOVERY_URL"
      }
    },
    "provider_config": {
      "vke_configuration": {
        "vke_cluster_id": "YOUR_VKE_CLUSTER_ID",
        "namespace": "YOUR_VKE_NAMESPACE",
        "workspace_id": "default"
      }
    }
  }
}
```

## 常见问题

如果再次执行 `create` 时没有重新创建 Runtime，通常是因为 state 文件里已经有 `runtime_id`。这是脚本的防重复创建逻辑。确认要新建 Runtime 时，请先检查并备份旧 state 文件，再指定新的 `--state` 路径或清理旧 state。

如果出现 `No module named 'requests'`，说明当前 Python 环境还没有安装依赖。可以执行：

```bash
uv add requests
uv run python create_vke_runtime.py get --config config.json
```

或：

```bash
pip install -r requirements.txt
python3 create_vke_runtime.py get --config config.json
```
