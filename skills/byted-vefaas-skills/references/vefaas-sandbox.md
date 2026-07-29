# 沙箱管理

本页用于指导如何使用 `vefaas sandbox` 管理沙箱应用和沙箱实例。重点是理解“预热镜像 -> 沙箱应用 -> 沙箱实例”的流程；具体参数以 `vefaas sandbox <command> --help` 为准。

## Sandbox 模型

沙箱是一种特殊/定制的函数。它的 Function、Revision、Instance 模型和普通函数类似，但创建和运行方式不同：

- **Sandbox application**：沙箱应用，本质上是 `FunctionType=sandbox` 的函数资源，用来定义镜像、启动命令、端口、环境变量、资源规格和发布版本。
- **Sandbox revision**：沙箱应用的镜像和配置版本。修改镜像、启动命令、端口、环境变量或资源规格后，需要发布 revision 才会影响后续实例。
- **Sandbox instance**：从沙箱应用主动创建出来的隔离运行实体。它不是由请求流量自动扩缩容出来的普通函数实例。
- **预热镜像**：沙箱必须基于已预热镜像创建，预热后才能达到秒级拉起实例的效果。

沙箱主要面向代码沙箱、浏览器/计算机沙箱、模型评测、临时隔离执行环境等场景。用户要的是部署网站/API 或普通函数动态扩缩容时，不要走沙箱工作流。

## 常见使用流程

### 1. 选择或预热镜像

创建沙箱应用前，必须先确认可用镜像。沙箱镜像列表只表示“已经预热、可以直接用于创建沙箱”的镜像，不等同于用户 CR 里的全部容器镜像。

沙箱镜像分两类：

- **公有镜像**：平台提供并已预热的镜像，可按 image group / status / image URL / image ID 查询。适合快速创建沙箱应用。
- **私有镜像**：用户自己提交过预热任务并已进入沙箱镜像列表的镜像。只有预热成功后，才适合用于创建沙箱应用。

查询已预热镜像时，只给用户推荐最短路径：

```bash
vefaas sandbox images public
vefaas sandbox images private
```

需要按类别、状态、镜像地址或 ID 过滤时，再查看 `vefaas sandbox images public --help` 或 `vefaas sandbox images private --help` 后补充参数；不要把所有过滤命令一次性塞给用户。

如果用户已经给出完整镜像地址，可以直接提交预热；提交后用私有镜像列表观察 `caching` / `success` / `failed` 状态：

```bash
vefaas sandbox images precache <image-url>
vefaas sandbox images private --status success
```

如果用户想从火山引擎 CR 里选择镜像，先按控制台同样的层级逐步缩小范围：registry -> namespace -> repository -> tag。`vefaas cr` 只浏览用户 CR 里的原始镜像，不会预热；只有提交 sandbox 预热并成功后，镜像才会出现在 `vefaas sandbox images private` 中。不要一次性列出所有 CR 子命令；先从 registry 或 `cr --help` 开始：

```bash
vefaas cr registries
vefaas cr --help
```

从 CR 选择镜像并预热到 sandbox 时，先用 `vefaas cr tags` 找到镜像 tag，拼出完整镜像 URL，再用通用预热入口提交：

```bash
vefaas cr tags --registry <registry> --namespace <namespace> --repository <repository>
vefaas sandbox images precache <image-url> --registry <registry>
```

CR tag 列表默认只展示 Linux/amd64 镜像。除非用户明确知道镜像架构和平台限制，不要引导使用非 Linux/amd64 镜像。

CLI 在提交 CR 镜像预热前会先调用 `GetImageConfig` 验证镜像可访问性。只有 `GetImageConfig` 超时、镜像地址看似无效或提示 internal service timeout 时，才可能需要 CR VPC tunnel；不要仅根据 registry 类型或 tunnel 查询状态判断。遇到这类问题时，带上具体镜像地址检查，确认需要后再打通：

```bash
vefaas cr tunnel --registry <registry> --image-url <image-url>
vefaas cr tunnel --registry <registry> --image-url <image-url> --enable --wait
```

也可以让预热命令仅在 `GetImageConfig` 判定需要时自动尝试打通：

```bash
vefaas sandbox images precache <image-url> --registry <registry> --enable-cr-tunnel
```

如果 `GetImageConfig` 成功，直接提交预热，不要执行 tunnel enable；部分 registry 类型不支持该操作。

删除沙箱镜像指删除“沙箱镜像预热记录”，不是删除用户 CR 仓库里的原始镜像。删除前必须确认 image ID；如果预热记录已被沙箱应用引用，CLI 会返回正在使用它的沙箱应用，先处理相关沙箱应用后再删除：

```bash
vefaas sandbox images delete --id <image-id> --yes
```

### 2. 创建沙箱应用

沙箱应用定义一类可反复拉起的运行环境。创建时需要确认镜像、启动命令、监听端口、CPU/内存、并发、超时、环境变量、IAM role、项目和标签等配置。沙箱对外 HTTP 访问入口在控制台称为“网关路由配置”，底层只支持 APIG。

用 `vefaas sandbox create` 创建沙箱应用。创建后先用 `vefaas sandbox info` 确认应用 ID、镜像、命令、端口和 runtime 信息。后续所有实例操作都要使用 sandbox application ID。

创建沙箱应用时也可以同时指定网关路由配置；只有需要线上 HTTP 访问入口时才传这些参数，单纯 TestInvoke 不需要：

```bash
vefaas sandbox create --name <sandbox-name> --image-id <image-id> --gateway-id <gateway-id> --route-path /sandbox
vefaas sandbox create --name <sandbox-name> --image <image-url> --gateway-name <gateway-name> --gateway-service-name <service-name> --route-name <route-name>
```

常用网关路由参数包括 `--gateway-id` / `--gateway-name`、`--gateway-service-id` / `--gateway-service-name`、`--route-name`、`--route-path`、`--route-methods`、`--route-timeout` 和 `--route-cors`。如果传了 route 相关参数但没有指定 gateway，CLI 应先报参数错误，不应先创建沙箱应用。

### 3. 更新配置并发布 Revision

沙箱应用的配置和镜像变化会形成新的版本语义。修改应用级配置时，用 `vefaas sandbox config` 或 `vefaas deploy --sandboxId`，然后用 `vefaas sandbox release` 发布新 revision。

发布前确认变更是否会影响后续新建实例。已存在实例是否受影响取决于平台行为和实例状态；不要默认所有运行中实例都会自动切换到新 revision。

### 4. 主动创建沙箱实例

沙箱实例需要主动创建，适合一次任务、一次会话或一次评测运行环境。创建实例时可以按需覆盖超时、CPU/内存、并发、请求超时、环境变量、metadata、session，必要时也可以覆盖实例镜像、命令和端口。

用 `vefaas sandbox instance create` 创建实例，用 `vefaas sandbox instance list` / `describe` 确认实例状态。sandbox application ID 和 instance name/ID 不是同一个概念，不能混用。

如果创建实例返回 `function_cold_start_timeout`、`internal_load_request_error` 或提示 `load sandbox cost ... timeout`，这通常表示实例启动/冷启动失败，不是普通网络问题。优先从错误信息里复制 `X-Faas-Instance-Name`，再用 `vefaas sandbox instance describe --id <sandbox-application-id> --instance <instance-name>` 和 `vefaas sandbox logs --id <sandbox-application-id> --instance <instance-name>` 查看实例状态和日志，同时检查沙箱应用的镜像、启动命令、端口、资源、环境变量和已发布 revision。

### 5. 访问特定实例

沙箱应用下的多个实例通常共享访问域名。访问特定实例时，可使用 `x-faas-instance-name` 请求头或 `faasInstanceName` 查询参数定位实例。

如果需要为沙箱对外提供 HTTP 访问入口，需要确认沙箱应用的网关路由配置。沙箱只能绑定 APIG，绑定、route 编辑、APIG 权限不足处理见 [触发器与 APIG Route](vefaas-trigger.md)。如果只是测试调用沙箱函数，不需要先绑定触发器。

### 6. 管理实例生命周期

沙箱实例生命周期可显式管理：

- **pause/resume**：暂停和恢复实例，适合临时保留状态但停止运行的场景。
- **timeout**：查询或调整实例过期时间，适合长任务或会话续期。
- **kill**：销毁实例，属于高风险操作，必须确认 sandbox application ID 和 instance name。
- **webshell/logs**：进入实例或查看日志，用于调试运行环境和任务问题。

实例管理类操作前，先用 `vefaas sandbox instance list` 确认目标实例；不要凭用户口述的名称直接 pause、resume 或 kill。

### 7. 排障顺序

沙箱创建、访问或执行失败时，按下面顺序排查：

1. 确认镜像是否已预热成功，image ID / image URL 是否匹配。
2. 用 `vefaas sandbox info` 检查沙箱应用的镜像、启动命令、端口、资源和 revision。
3. 用 `vefaas sandbox instance list` / `describe` 检查实例状态。
4. 遇到 `function_cold_start_timeout` / `internal_load_request_error` 时，从错误里的 `X-Faas-Instance-Name` 定位实例，再查看实例详情和日志。
5. 通过实例日志或 WebShell 排查启动失败、端口错误、依赖缺失、权限或业务逻辑问题。
6. 必要时更新沙箱应用配置并发布新 revision，再创建新实例验证。

删除沙箱应用、删除镜像预热记录、kill/pause/resume 实例都可能影响正在运行的任务，执行前必须确认资源 ID 和用户意图。
