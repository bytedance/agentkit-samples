# CreateHarness API 调用样例

本目录演示如何直接调用 Harness Infra 控制面 `CreateHarness` TOP API。
适合只验证 Harness 创建请求体、签名和接口返回，不包含 Endpoint、
Environment、Runtime、SessionStore 和 Session 的完整资源编排。

## 文件

| 文件 | 用途 |
| --- | --- |
| `CreateHarness.py` | 使用火山 AK/SK 签名并调用 `CreateHarness` |
| `CreateHarnessPayload.json` | 可直接提交的完整 `CreateHarness` 请求体示例 |

## 前置条件

- 已准备火山账号 AK/SK，并拥有 Harness Infra `CreateHarness` 权限。
- 已确认目标 Region，默认 `cn-beijing`。
- 如账号启用 Workspace 隔离，需要提供 `WorkspaceId`。
- 如果要绑定运行环境，需要提前准备可用的 `RuntimeId` 和 `EnvironmentId`。

凭据优先从命令行读取，也可使用环境变量：

```bash
export VOLCENGINE_ACCESS_KEY="..."
export VOLCENGINE_SECRET_KEY="..."
export VOLCENGINE_REGION="cn-beijing"
export AGENTKIT_WORKSPACE_ID="ws-xxxxxxxxxxxxxxxxxxxx"
```

如使用临时 STS 凭据，还需要设置：

```bash
export VOLCENGINE_SESSION_TOKEN="..."
```

## 运行

使用示例 JSON 请求体：

```bash
python CreateHarness.py --body-json-file CreateHarnessPayload.json
```

也可以通过参数生成请求体：

```bash
python CreateHarness.py \
  --name "api-demo-harness" \
  --model-id "doubao-seed-2-1-turbo-260628" \
  --model-base-url "https://ark.cn-beijing.volces.com/api/v3" \
  --runtime-id "r-xxxxxxxxxxxxxxxxxxxx" \
  --environment-id "env_xxxxxxxxxxxxxxxxxxxx"
```

提交前可先打印请求体，不访问网络：

```bash
python CreateHarness.py \
  --body-json-file CreateHarnessPayload.json \
  --dry-run
```

`--tools-json`、`--skills-json`、`--mcp-servers-json`、
`--knowledge-contexts-json`、`--payload-json` 和 `--metadata-json` 接收原始
JSON 字符串，便于临时覆盖请求体字段。

## 本地验证

验证相邻 Harness Infra 示例时，请使用目录 `requirements.txt` 中的固定依赖版本。
例如 `resource_to_chat_http` 测试依赖 `anthropic==1.5.0`；如果临时安装未固定的
新版 `anthropic`，SDK header 行为可能变化，导致相关测试误失败。

```bash
uv run --with rich --with requests --with pyyaml --with 'anthropic==1.5.0' \
  --with 'volcengine-python-sdk[ark]>=5.0.1,<6' \
  python -B -m unittest discover \
  -s ../resource_to_chat_http/tests -v
```

## 注意事项

- 不要提交真实 AK/SK、STS Token、模型 Key 或 Environment Key。
- `ClientToken` 只用于同一请求体的失败重试；修改请求体后应使用新的 token。
- `CreateHarnessPayload.json` 中的 ID 是占位值，真实调用前需要替换为目标账号下的资源 ID。
