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

其他必填字段示例：

```json
{
  "volcengine_region": "cn-beijing",
  "volcengine_agentkit_host": "agentkit-stg.cn-beijing.volcengineapi.com",
  "volcengine_agentkit_api_version": "2025-10-30",
  "volcengine_agentkit_service": "agentkit_stg",
  "artifact_url": "YOUR_IMAGE_URL",
  "role_name": "YOUR_RUNTIME_ROLE_NAME",
  "DiscoveryUrl": "YOUR_OIDC_DISCOVERY_URL",
  "namespace": "YOUR_VKE_NAMESPACE",
  "vke_cluster_id": "YOUR_VKE_CLUSTER_ID"
}
```

可选字段：

```json
{
  "x_forward_env": "",
  "min_instance": 1,
  "max_instance": 2,
  "WorkspaceId": ""
}
```

`WorkspaceId` 为空时不会放入 `CreateRuntime` 请求 body。

## 安装依赖

```bash
pip install -r requirements.txt
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

传入完整 body 时，脚本会直接使用该 body，不再根据 `artifact_url`、`role_name`、`DiscoveryUrl`、`namespace`、`vke_cluster_id` 自动构造。
