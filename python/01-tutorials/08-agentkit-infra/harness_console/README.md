# Harness Console

读取本地 `config.yaml` 的资源管理网页和 Python server。复用同级 `resource_to_chat_http/_clients.py` 的 TOP 签名、HTTP 错误处理与数据面客户端，以及 `_config.py` 的配置字段转换；不改写原示例的配置或状态文件。

## 启动

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。从当前目录运行：

```bash
uv run server.py
```

打开 <http://127.0.0.1:8765>。服务只监听本机 `127.0.0.1`。无需 Node.js 或前端构建。

默认配置选择顺序：

1. `--config /absolute/path/config.yaml`。
2. 环境变量 `HARNESS_INFRA_CONFIG`。
3. 上一级共享的 `../config.yaml`（路径按 server.py 所在目录解析）。
4. 当前 `harness_console` 目录原有的 `config.yaml`。
5. 同级 `../resource_to_chat_http/config.yaml`（兼容旧配置）。

配置格式复用上一级的 [config.yaml.example](../config.yaml.example)。首次使用可在本目录执行
`cp -n ../config.yaml.example ../config.yaml`，填写共享配置后供两个示例复用。
账号、地域、模型和资源默认配置在启动时读取，修改后需重启服务。脚本回写的 Session ID 和 Environment API Key 会在打开页面、刷新 Session 页或刷新数据面连接时重新读取，无需重启；若账号或地域变更，则阻止使用新会话凭据，提示先重启。

```bash
uv run server.py --config ../config.yaml --port 8765
```

不用 uv 时：

```bash
python -m pip install -r requirements.txt
python server.py --config ../config.yaml
```

控制面仍使用原脚本的 `HARNESS_INFRA_CONTROL_HOST`、`HARNESS_INFRA_CONTROL_SCHEME`、`HARNESS_INFRA_SERVICE`、`HARNESS_INFRA_API_VERSION`、地域及 AK/SK/STS 环境变量规则。`volcengine.access_key/secret_key/region` 优先来自 YAML，支持 `${ENV_NAME}`。HTTP 超时可通过 `HARNESS_INFRA_HTTP_TIMEOUT_SECONDS` 和 `HARNESS_INFRA_DATA_TIMEOUT_SECONDS` 调整。

## 快速开始

首页采用分组侧栏和四步引导：选择起点 → 配置 Harness → 配置 Environment → 开始第一次调用。

- 从本地配置开始：打开预填的 Harness 创建表单；每次创建前均可编辑并确认。
- 连接已有资源：选择 Active Harness、Environment、Ready 的 SERVERLESS_PG SessionStore 和绑定该存储的 Ready RuntimeTemplate，以及绑定同一环境和 Endpoint 的本地可用 API Key。
- 确认资源后，创建表单自动带入所选资源；创建 Session 成功后进入聊天页，由用户发送第一条消息。
- 所有资源的独立管理页面仍保留，包括 EnvironmentResource、状态筛选、Harness 归档和删除能力提示。图示中尚无接口支持的功能不展示。

创建异步资源后可使用“刷新资源”获取最新状态。返回快速开始会保留本次页面中的选择，刷新整个页面则重新开始。

## 支持的资源

EnvironmentResource 页面提供关联资源组的查询、创建、详情与删除，可通过 `EnvironmentId` 筛选所属环境。

| 资源 | Create | List / Get | Delete |
| --- | --- | --- | --- |
| Endpoint | `CreateEndpoint` | `ListEndpoints`；详情遍历列表按 `EndpointId` 匹配 | `DELETE /v1/endpoint/{id}`，需单独配置可信 REST 控制面入口 |
| Harness | `CreateHarness` | `ListHarnesses` / `GetHarness` | 当前 akx 未提供独立删除接口；保留禁用的删除按钮，独立归档按钮调用 `ArchiveHarness` |
| SessionStore | `CreateSessionStore` | `ListSessionStores` / `GetSessionStore` | `DeleteSessionStore` |
| RuntimeTemplate | `CreateRuntimeTemplate` | `ListRuntimeTemplates` / `GetRuntimeTemplate` | `DeleteRuntimeTemplate` |
| Environment | `CreateEnvironment` | `ListEnvironments` / `GetEnvironment` | `DeleteEnvironment` |
| Environment API Key | `CreateAPIKey` | `ListAPIKeys` / `GetAPIKey` | `DeleteAPIKey`，即撤销 |
| EnvironmentResource | `CreateEnvironmentResource` | `ListEnvironmentResources` / `GetEnvironmentResource` | `DeleteEnvironmentResource` |
| Session | `POST /v1/sessions` | `GET /v1/sessions` / `GET /v1/sessions/{id}` | 先 Archive，再 `DELETE /v1/sessions/{id}` |

控制面列出当前凭据账号、地域下的资源，不局限于原脚本创建的对象。列表支持服务端 JSON 筛选、下一页、加载全部；搜索框搜索已加载项。Harness 页面默认使用 `{"IncludeArchived": true}`，归档后记录仍显示为 `Archived`，可查看详情；可直接用状态下拉框选择全部、Active 或 Archived；RuntimeTemplate 和 Session 也提供各自的状态下拉筛选。状态条件在服务端分页前生效，并与高级 JSON 筛选同步。Environment 的归档对象需用 `{"IncludeArchived": true}`，已删除 EnvironmentResource 需用 `{"IncludeDeleted": true}` 查询。Session 管理列表默认包含归档项；聊天页仍只列出未归档会话。

SessionStore 对齐最新 `resource_to_chat_http` 示例：按 `session_store.project_name` 和 `session_store.network` 预填托管 `SERVERLESS_PG` 创建请求。未填写 `session_store` 的旧配置使用项目 `default` 和公网模式。私网模式需要 `VpcConfig.VpcId` 和恰好一个 `SubnetIds`；可在完整请求 JSON 中编辑。

SessionStore 列表按 `SessionStores/NextToken` 分页，支持 `ProjectName`、`Filters` 和创建时间的高级 JSON 筛选。Create/DeleteSessionStore 不附加 `ClientToken`，创建超时后应先查询列表再决定是否重试。

新建 RuntimeTemplate 必须选择 Ready 的 SERVERLESS_PG SessionStore，服务端提交前会再次查询并检查状态，随后原样传递 `SessionStoreId`。快速开始按 SessionStore 筛选绑定它的 Ready 模板；该绑定只放在 RuntimeTemplate，不添加到 Session 请求。旧模板仍可在资源页查询和 Session 创建表单中选择，控制台不修改既有绑定或迁移数据。

删除顺序应为 Session → RuntimeTemplate → SessionStore；Environment 的 EnvironmentResource 等依赖仍需单独清理。控制台不自动级联删除，受理后需要刷新确认最终状态。

创建窗口预填模型、工具、计算规格等本地配置。基础表单与完整 JSON 双向同步，展开 JSON 可修改其余 API 字段。模板 `Envs`、环境 `EnvVars` 默认在服务端继承，避免将本地配置密钥带到浏览器；在完整 JSON 显式填写空对象可清空。页面中的删除操作需输入准确资源 ID；删除 RuntimeTemplate 还须填写 `Reason`（去首尾空白后 1～1024 UTF-8 字节）。同一弹窗原样重试保留 ClientToken，修改原因后生成新 token。

云资源可能异步创建或删除。请求成功后应刷新列表/详情确认 `Ready`、`Active` 或 `404`；受理并不表示底层实例已经创建或删除完毕。删除有依赖的资源可能返回冲突，不自动级联删除其他资源。

### Endpoint 删除边界

akx 的公开 TOP 契约没有 `GetEndpoint` / `DeleteEndpoint` Action。已有 `DELETE /v1/endpoint/:endpoint_id` 是 REST 控制面路由，不能直接发给普通 TOP Action 地址，也不能使用 Environment API Key 代替账号认证。

若部署提供了通过 AK/SK 签名认证、能路由到该 REST 接口的可信控制面网关，可在配置里添加：

```yaml
console:
  control_rest_base_url: "https://your-control-gateway.example.com"
```

server 使用当前 AK/SK、地域、service 对真实 DELETE 路径签名，保留入口路径前缀；不注入账号身份头、不更改网关认证。不配置时明确禁用 Endpoint 删除按钮。这个入口是否部署、是否允许删除 TOP 创建的账号绑定 Endpoint，需要由实际网关与后端能力决定；本次没有进行云端删除验证。

### Session 与聊天

1. 打开「Session」或「Session 聊天」。
2. 选择 Endpoint，再选择其绑定的 Environment API Key。Session 列表限定在所选 Key 的环境；切换 Key 可查看其他环境，不将缺少凭据的环境误报为空。
3. 原配置 `environment.env_api_key.id/value` 可直接复用。其他已有 Key 需通过「导入密钥」提供明文，或者在 API Key 资源页创建一个新 Key。控制面 Get/List 不返回已有 Key 明文。
4. 创建 Session 时选择 Active Harness、Ready RuntimeTemplate 和相同 Environment；`x-ark-key-name` 使用配置中的 `harness.model.api_key_name`，也可在创建窗口修改。它是方舟模型 Key 的 **Name**，不是 Environment Key 或模型密钥明文。
5. 选择 Session 读取历史，输入问题发送。页面调用 `POST /v1/sessions/{id}/events`，再按 `after_sequence` 分页轮询持久化事件，展示消息和可展开的工具/状态/错误事件。文本以持久化消息更新，不是逐 token 的 SSE 预览。
6. `session.status_idle` 的 `stop_reason.type=end_turn` 才表示轮次结束。`requires_action`、错误、终止、超过五分钟未完成都会明确显示；页面不自动批准工具确认。停止等待只停止本地轮询，不取消服务端任务；重新选择 Session 可重读历史。

控制面创建使用稳定 `ClientToken`（Endpoint 不支持该字段），Session 创建使用 `Idempotency-Key`，聊天使用稳定事件 ID。未确认发送结果时，原样重试复用事件 ID；编辑内容产生新 ID。资源创建失败后在同一弹窗原样重试复用 token。关闭弹窗后不保留 token，应先查询资源状态再重新创建。HTTP 客户端关闭自动重试，避免非幂等 Endpoint 创建因网络重试而重复。

## 本地凭据与文件

- AK/SK、环境 Key 明文留在 Python 服务端，不放入浏览器 localStorage、URL 或访问日志。响应会脱敏凭据字段，浏览器使用同源随机令牌调用固定的本地操作入口。服务重启导致令牌失效时，页面会重新读取令牌；仅对本地在转发前明确拒绝的请求重试一次，不自动重试结果不确定的云端操作。
- 新建或导入的环境 Key 保存在 `.local/keys-<scope>.json`，文件权限 `0600`；按配置路径、控制面范围和 AK 区分。该文件与本地 `config.yaml` 都被 Git 忽略。请勿删除唯一密钥副本；云端无法通过 Get 找回明文。
- Endpoint 数据面 URL 和 Key 的绑定从控制面读取，浏览器不能指定任意目标 URL 携带密钥。
- 配置与云端返回的文本按纯文本显示，不执行 HTML。服务不输出请求正文、聊天内容或凭据。
- 环境网络、镜像和 packages 按当前公开字段转换；RuntimeTemplate 公开契约没有网络字段，原配置 `runtime_template.network` 不会发送。没有自动创建 IAM Role、部署网关、配置套餐/配额或执行原示例的一键资源链。

## 一键清理

侧栏「维护 → 一键清理」→ 扫描资源 → 筛选并勾选（或全选可见资源）→ 清理所选资源。确认弹窗展示完整执行清单，填写原因并输入 `清理 N 项` 后才执行。

- 扫描当前账号、地域的全部分页；Harness 包含归档记录，Session 使用本机已保存或 config.yaml 中的密钥，逐环境扫描并包含归档 Session。默认不勾选任何资源。
- 未提供有效密钥的环境会显示扫描缺口，禁止清理涉及该环境的资源，以及无法排除引用关系的模板、存储、Harness 和 Endpoint；先导入密钥再扫描。控制面列表失败会禁止整次执行。
- 已知依赖未被勾选时提示补选，不自动扩大清理范围。执行顺序为 Session、RuntimeTemplate、SessionStore、EnvironmentResource、API Key、Environment、Harness 归档、Endpoint。
- Harness 只有归档，已归档记录不可永久删除。Endpoint 未配置可信 REST 删除网关时不可选。
- 每项删除等待查询确认不存在（404）或 Deleted；Harness 等待 Archived。请求受理不算完成。失败或约四分钟轮询超时后暂停后续操作，不自动重试删除请求。列表是扫描快照，云端并发变化仍可能导致依赖冲突。
- 点击停止只停止本地后续请求，不撤销已受理的云端操作。执行期间保持页面打开；关闭页面会中断本地编排。再次执行前必须重新扫描，完成数仅代表本次勾选清单。

批量逻辑离线测试：`node --test tests/cleanup.test.cjs`。这些测试使用模拟资源，不会清理真实云端资源。

## 本地验证

```bash
uv run --with requests --with pyyaml python -B -m unittest discover -s tests -v
uv run --with requests --with pyyaml --with playwright python -B tests/browser_smoke.py
uv run --with ruff ruff check .
uv run --with ruff ruff format --check .
node --check static/app.js
```

浏览器测试需要已安装 Google Chrome；它会启动本地模拟上游与独立临时配置，不触碰云端资源，截图写入忽略的 `.local/`。

2026-10-16 验证结果：

- 15 项本地 HTTP 协议测试通过：资源 CRUD、分页/异常游标、签名、Session 创建/归档删除、事件幂等与 end_turn、密钥持久化与脱敏、绑定隔离、同源访问限制。
- Chrome 浏览器操作通过：分页、详情、创建、归档、Session 聊天、移动端宽度检查；无浏览器脚本错误。
- 使用现有本地配置对云端执行只读列表查询通过：Endpoint 1、Harness 2、RuntimeTemplate 2、Environment 2、API Key 1、EnvironmentResource 2、所选环境 Session 1。数量是当时快照。
- 真实配置下 Chrome 只读验证通过：Endpoint 列表、Session 列表和历史消息加载正常，浏览器无脚本错误。
- 云端创建/删除、云端 REST Endpoint 删除以及真实模型聊天 **未执行**。本地模拟测试不代表云端端到端通过。

## 源码契约依据

对照相邻工作区 `ak-x/akx`：

- `apis/harness-infra/api.proto`：TOP Action 与 REST 路由。
- `apis/harness-infra/message.proto`：PascalCase 控制面请求、分页和资源对象；snake_case Session/Event。
- `internal/harness-infra/server/plane.go`：Endpoint REST 属于控制面。
- `internal/harness-infra/service/endpoint.go`、`usecase/endpoint.go`：Endpoint 查询与删除边界。
- `docs/harness-infra/api/{endpoint,harness,environment,api-key,environment-resource,runtime-template,session}-api.md`：资源约束、会话状态、事件和异步删除语义。

这些源码目录仅用于核对接口；运行本示例不依赖 akx 的 Go 环境。
