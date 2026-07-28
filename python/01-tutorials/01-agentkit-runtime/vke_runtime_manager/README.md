# VKE Runtime Manager

这个示例用于通过 AgentKit OpenAPI 创建 VKE Runtime，并查询 Runtime 状态。

脚本提供两个常用命令：

- `create`：创建 Runtime。创建成功后每 10 秒查询一次状态，最多等待 5 分钟，直到状态变为 `Ready`。
- `get`：查询已有 Runtime 状态。默认读取本地 state 文件里的 `RuntimeId`，也可以手动传入。

## 准备配置

复制示例配置：

```bash
cp config.example.json config.json
```

编辑 `config.json`，至少填写这些字段。

凭证字段请只在本地 `config.json` 中填写，不要提交到代码仓库：

- `volcengine_access_key`
- `volcengine_secret_key`

必填字段示例：

```json
{
  "volcengine_region": "cn-beijing",
  "volcengine_agentkit_host": "agentkit-stg.cn-beijing.volcengineapi.com",
  "volcengine_agentkit_api_version": "2025-10-30",
  "volcengine_agentkit_service": "agentkit_stg",
  "name": "sch-hia1",
  "artifact_url": "YOUR_IMAGE_URL",
  "role_name": "YOUR_RUNTIME_ROLE_NAME",
  "DiscoveryUrl": "YOUR_OIDC_DISCOVERY_URL",
  "namespace": "YOUR_VKE_NAMESPACE",
  "vke_cluster_id": "YOUR_VKE_CLUSTER_ID"
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `volcengine_access_key` | 火山引擎 AK。 |
| `volcengine_secret_key` | 火山引擎 SK。 |
| `volcengine_region` | AgentKit 服务地域，例如 `cn-beijing`。 |
| `volcengine_agentkit_host` | AgentKit 服务域名，例如 `agentkit.cn-beijing.volcengineapi.com`。 |
| `volcengine_agentkit_api_version` | AgentKit OpenAPI 版本。 |
| `volcengine_agentkit_service` | AgentKit 服务名称，线上环境为 `agentkit`。 |
| `x_forward_env` | 测试环境标识，线上环境不传。 |
| `name` | Agent Runtime 名称前缀。 |
| `artifact_url` | 镜像地址。 |
| `role_name` | 火山引擎 IAM Role 名称。 |
| `DiscoveryUrl` | OAuth/OIDC IdP discovery URL。 |
| `namespace` | VKE 集群 namespace。 |
| `vke_cluster_id` | VKE 集群 ID。 |
| `WorkspaceId` | CP 服务工作区，未配置时默认为 `default`。 |
| `min_instance` | AgentKit Runtime 最小实例数。 |
| `max_instance` | AgentKit Runtime 最大实例数。 |

可选字段：

```json
{
  "x_forward_env": "",
  "min_instance": 1,
  "max_instance": 2,
  "WorkspaceId": "default"
}
```

`WorkspaceId` 未配置或为空时会使用 `default`。
`name` 是 Runtime 名称前缀，创建时脚本会统一拼接时间戳，最终名称格式为 `<name>-YYYYmmddHHMMSS`。为兼容已有配置，平铺配置也支持字段名 `runtime_name` 和 `runtimename`。
`x_forward_env` 为空时不会放入请求 header。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 查看帮助

```bash
python3 create_vke_runtime.py -h
python3 create_vke_runtime.py create -h
python3 create_vke_runtime.py get -h
```

## 创建 Runtime

```bash
python3 create_vke_runtime.py create --config config.json
```

脚本会在本地写入 state 文件：

```bash
config.json.vke-runtime-state.json
```

再次执行 `create` 时，如果 state 里已有 `RuntimeId`，会跳过创建，直接查询状态，避免重复创建 Runtime。

## 查询 Runtime

使用 state 文件里的 `RuntimeId`：

```bash
python3 create_vke_runtime.py get --config config.json
```

手动指定 `RuntimeId`：

```bash
python3 create_vke_runtime.py get --config config.json --runtime-id r-xxxx
```

## 使用完整 Body

如果你已经有完整的 `CreateRuntime` body，可以放在单独文件里：

```bash
python3 create_vke_runtime.py create --config config.json --body-file body.json
```

传入完整 body 时，脚本会直接使用该 body，不再根据 `artifact_url`、`role_name`、`DiscoveryUrl`、`namespace`、`vke_cluster_id` 自动构造。body 中的 `name` 同样作为 Runtime 名称前缀，创建时会统一拼接时间戳，最终名称格式为 `<name>-YYYYmmddHHMMSS`。

完整 body 文件必须是合法 JSON，不支持 Python 注释。必填字段为：

- `name`
- `artifact_url`
- `role_name`
- `authorizer_configuration.CustomJwtAuthorizer.DiscoveryUrl`
- `provider_config.vke_configuration.vke_cluster_id`
- `provider_config.vke_configuration.namespace`

`min_instance`、`max_instance`、`provider_config.vke_configuration.WorkspaceId`、`provider_config.vke_configuration.nas_mount_configs` 为选填字段。

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
  "authorizer_configuration": {
    "CustomJwtAuthorizer": {
      "DiscoveryUrl": "https://userpool-a95b65a4-5396-417a-a40f-79b266db0108.userpool.auth.id.cn-beijing.volces.com/.well-known/openid-configuration"
    }
  },
  "provider_config": {
    "vke_configuration": {
      "vke_cluster_id": "cd59nk5v1a4b3d2hchpmg",
      "namespace": "hiagent",
      "WorkspaceId": "YOUR_WORKSPACE_ID",
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
