# 函数管理

本页用于指导如何使用 `vefaas fn` 管理函数。重点是理解函数类型、代码形态和常见生命周期；具体参数以 `vefaas fn <command> --help` 为准。

## Function 模型

函数是 veFaaS（函数服务）的核心资源，承载代码或镜像、运行时、启动命令、端口、环境变量、CPU/内存、并发、超时、触发器、版本、实例、任务、日志和监控。

- **Function**：函数资源本身，是用户主要创建和管理的对象。
- **Revision**：函数代码/镜像和配置形成的版本快照，发布、回滚围绕 revision 展开。
- **Instance**：运行 revision 的实际执行单元，普通函数实例通常由平台按请求流量和扩缩容策略动态创建或回收。
- **策略**：函数可以配置实例上下限、预留实例、定时/弹性扩缩容等策略；CLI 高阶命令只覆盖部分能力，复杂策略先查 help 或 OpenAPI 参数结构。

## 函数类型

创建函数前，先确认用户想要的运行形态。CLI 支持四类函数：

| 类型 | 适用场景 | 特点 |
| --- | --- | --- |
| `runtime` | 事件函数、轻量逻辑、SDK runtime 代码 | 使用 Python/Node.js/Go 等托管 runtime，不强调常驻服务端口，适合事件驱动调用。 |
| `webserver` | HTTP Web 服务、API 服务、容器化 Web 应用 | 默认类型，基于 `native/v1`，有启动命令和监听端口，通常通过触发器对外访问。 |
| `microservice` | 需要常驻的微服务 | 基于 `native/v1`，CPU 策略默认偏常驻，适合不希望频繁冷启动的服务形态。 |
| `job` | 异步任务、批处理、长耗时任务 | 默认独占执行，单实例并发较低，适合任务型调用和更长超时。 |

不确定类型、runtime、source、资源规格或高级参数时，先运行 `vefaas fn create --help`，不要猜参数。

## 代码与镜像形态

函数通常有两种代码管理方式：

- **纯镜像函数**：以完整容器镜像作为 source，镜像内包含运行环境和业务代码。CLI 可以创建和更新配置，但不适合用 `pull` / `push` 管理代码包。
- **基础镜像/托管 runtime + 代码包**：函数基于平台 runtime 或基础运行环境，业务代码由 CLI 从本地目录、zip 或 TOS 上传。CLI 用户通常在本地维护这份代码。

使用 CLI 创建函数时，可以从本地目录、zip、TOS 或镜像创建。交互式创建或模板化创建通常会生成/携带一份默认代码；后续常见流程是在本地修改代码，再用 `vefaas fn push` 上传更新，或用 `vefaas deploy --funcId <function-id>` 完成构建、上传和发布链路。

函数镜像 source 直接来自用户 CR，不走沙箱预热镜像。需要从 CR 选择镜像时，优先使用 `vefaas fn create --source-type image`，CLI 会按 registry -> namespace -> repository -> tag 选择，并读取镜像配置回填启动命令、端口和环境变量。需要先浏览 CR 原始镜像时，从 `vefaas cr registries` 或 `vefaas cr --help` 开始；这里不会触发沙箱预热。函数镜像当前只支持 `linux/amd64`；遇到非支持架构 tag 时，应换一个 tag 或重新构建镜像。

如果浏览 CR 时遇到 `AccessDenied: API access denied`，且错误中包含 `Target:"cr"`、`Action:"ListRegistries"` / `ListNamespaces` / `ListRepositories` / `ListTags`，不要反复重试同一个凭据。SSO 登录通常需要切换 AK/SK；AK/SK 仍失败时，让用户联系管理员补充 Container Registry（CR）OpenAPI 权限。AK/SK 管理页：https://console.volcengine.com/iam/keymanage

CR 镜像选择后，CLI 会先调用 `GetImageConfig` 读取镜像配置。只有它超时、镜像地址看似无效或提示 internal service timeout 时，才可能需要 CR VPC tunnel；不要仅根据 registry 类型或 tunnel 查询状态判断。此时带上具体镜像地址检查，确认需要后再启用：

```bash
vefaas cr tunnel --registry <registry> --image-url <image-url>
vefaas cr tunnel --registry <registry> --image-url <image-url> --enable --wait
```

如果 `GetImageConfig` 成功，直接创建函数，不要执行 tunnel enable；部分 registry 类型不支持该操作。

镜像函数创建后，平台会异步同步并缓存 source image。镜像同步完成前不能发布 revision；如果刚创建完立刻发布遇到 `Source image sync is in Running status`，这通常表示需要等待，不代表函数创建失败。`vefaas fn release` 会自动查询 `GetImageSyncStatus` 并等待镜像同步和缓存就绪；也可用 `vefaas fn info --id <function-id>` 查看 `ImageSyncStatus`、`ImageCacheStatus` 和 `ImageReadyForRelease`。

## 常见使用流程

### 1. 定位或创建函数

已有函数时，先用 `vefaas fn list` / `vefaas fn info` 确认函数 ID、类型、source、runtime、端口和当前配置。涉及写操作时优先使用函数 ID，不要只凭名称操作。

新建函数时，用 `vefaas fn create`。创建前先根据上面的四种类型选择 `--type`，再确认 source 形态：

- 本地代码或 zip：适合后续继续用 CLI 管理代码。
- 镜像 source：适合已有完整容器镜像的服务。
- TOS source：适合已有代码包上传位置的场景。

如果用户要从 CR 创建纯镜像函数，用 `vefaas fn create --source-type image` 进入交互选择；非交互时可传 `--cr-registry`、`--cr-namespace`、`--cr-repository` 和可选 `--cr-tag`。具体参数以 `vefaas fn create --help` 为准。

### 2. 本地修改并推送代码

CLI 用户通常会在本地管理函数代码。已有函数可以用 `vefaas fn pull` 拉取代码到本地；镜像类型函数不支持这种代码拉取方式。

修改代码后，如果只想上传代码包，用 `vefaas fn push`。`push` 只负责上传，不等同于发布上线；用户说“发布、上线、部署”时，应继续执行发布动作，或使用 `vefaas deploy --funcId <function-id>` 走完整部署链路。

纯镜像函数不涉及代码包，不能使用 `fn push`；创建或更新镜像函数后直接执行 `vefaas fn release`，CLI 会先等待镜像同步和缓存就绪。

### 3. 更新函数配置

函数配置包括启动命令、端口、CPU/内存、并发、超时、环境变量、VPC、IAM role、标签等。简单配置可用 `vefaas fn config` 和 `vefaas fn env` 更新；复杂 JSON 配置先查 `vefaas fn config --help`。

更新 secret 类环境变量时，不要把值明文回显给用户。生产函数调整资源规格、实例上下限或扩缩容策略前，先确认当前配置和预期影响。

### 4. 安装依赖并发布

代码上传后，如 runtime 或代码包需要云端依赖安装，使用 `vefaas fn deps` 相关命令确认依赖安装成功。依赖安装能力和参数可能随 source/runtime 不同而变化，先看 `vefaas fn deps --help`。

确认代码和配置无误后，用 `vefaas fn release` 发布新 revision。镜像函数发布前会自动等待 source image 同步和缓存就绪；如果同步失败，先用 `vefaas fn info --id <function-id>` 查看状态并检查镜像地址、权限和 CR 可访问性。发布后可用 `vefaas fn revision` 查看版本信息。若发布后发现问题，用 `vefaas fn rollback` 回滚到指定 revision；回滚前必须确认函数 ID 和目标 revision number。

### 5. 测试调用

发布后先用 `vefaas fn invoke` 做测试调用。Invoke 是函数 TestInvoke 调用，不依赖触发器；即使函数没有绑定 APIG、Timer 或其他触发器，也可以 invoke 测试函数。

事件函数通常传入事件 payload：

```bash
vefaas fn invoke --id <function-id> --data '{"hello":"vefaas"}'
```

HTTP/Webserver 形态可以用 method、path、header/body 或 request JSON 模拟 HTTP 请求。这里的 APIG-shaped 参数只是测试调用参数格式，不代表线上已经存在 APIG route：

```bash
vefaas fn invoke --id <function-id> --method GET --path /v1/ping
vefaas fn invoke --id <function-id> --method POST --path /api --header 'content-type=application/json' --data '{"x":1}'
vefaas fn invoke --id <function-id> --requestJson '{"data":{},"method":"GET","path":"/","headers":{}}'
```

调试实例调用：

```bash
vefaas fn invoke --id <function-id> --method GET --path / --debug-instance
```

`--debug-instance` 会注入 `x-faas-debug-instance=true`。不要手写这个 header，除非用户明确要求复现底层请求。

如果调用失败，先看错误信息、函数实例状态和日志，再决定是否修改配置、重新发布或回滚。调用返回 `ResourceNotFound` 时，先判断是否是账号/环境不一致：用 `vefaas login --check` 确认登录方式和环境，用 `vefaas fn info --id <function-id>` 或 `vefaas fn list --fields Id,Name --limit 20` 确认当前账号是否能看到该函数。

### 6. 绑定触发器并对外访问

如果函数需要对外提供访问地址，需要绑定 APIG 触发器，基于已有 gateway 实例创建或关联 APIG 资源。Timer、Kafka、RocketMQ、BMQ、TLS 这类函数触发器也有类型化 CRUD 命令；TOS 仍属于跨服务 Bucket Notification 场景，不要假设高阶命令已覆盖。绑定、编辑 route、确认访问 URL、处理 APIG 权限不足或管理非 APIG 触发器前，必须先读 [触发器与 APIG Route](vefaas-trigger.md)。

### 7. 任务、发布记录与扩缩容策略

异步任务、发布记录和扩缩容策略已经有高阶命令，优先查 help 后再执行写操作：

```bash
vefaas fn task list --id <function-id> -o table
vefaas fn task terminate --id <function-id> --task-id <task-id>
vefaas fn release-record list --id <function-id> -o table
vefaas fn release-record status --id <function-id> --record-id <record-id>
vefaas fn strategy elastic list --id <function-id> -o table
vefaas fn strategy cron list --id <function-id> -o table
```

更新弹性策略、创建/更新/删除定时策略会影响线上实例容量和成本。执行前先确认函数 ID、当前策略和预期变更；复杂 payload 不要猜字段，先运行 `vefaas fn strategy --help`、`vefaas fn strategy elastic --help` 或 `vefaas fn strategy cron --help`。

### 8. 查看实例日志排障

线上请求异常时，先用 `vefaas fn instances` 找到相关实例，再用 `vefaas fn logs` 查看实例日志。需要进入运行环境排查时，可用 `vefaas fn webshell`，但应避免泄露日志、环境变量或连接串中的敏感信息。

常见排障顺序：

1. 确认函数 ID、当前 revision 和发布状态。
2. 用 `invoke` 复现问题。
3. 查看实例状态和日志。
4. 检查环境变量、启动命令、端口、资源规格和依赖安装状态。
5. 必要时修复后重新 push/release，或 rollback 到稳定 revision。
