# 应用工作流

本页用于指导如何用 `vefaas` 把本地项目、模板项目或已有应用发布成可访问的 veFaaS Application。重点是理解应用模型和发布流程；具体参数以 `vefaas <command> --help` 为准。

## 目录

- [Application 模型](#application-模型)
- [常见使用流程](#常见使用流程)
- [应用查询与管理](#应用查询与管理)

## Application 模型

应用是在函数基础上编排应用级逻辑后包装成的产品形态，适合用户想“把项目发布成可访问的应用”，而不是只管理一段函数代码。

- **Application**：面向业务交付的应用资源，负责聚合发布、访问入口和依赖资源视角。
- **Backing Function**：应用底层关联的函数，真正承载代码/镜像、运行时、环境变量、实例和日志。
- **访问入口**：应用通常会关联 APIG 触发器和访问 URL，让用户可以通过 HTTP 请求访问服务。
- **版本与部署记录**：应用维度会管理整体版本、部署记录和发布状态；底层仍会更新关联函数的代码、配置和 revision。
- **Git 自动触发部署**：应用产品形态可以承载代码仓库关联、Webhook 触发和持续部署记录。CLI 当前主要覆盖本地项目/模板项目的创建、绑定、部署、配置和访问 URL 查询。

CLI 创建新应用时，会先创建底层函数，再创建应用并关联该函数。本地配置中 `application.id` 是应用 ID，`application.function_id` 是底层函数 ID；应用工作流里不要把两个 ID 混用。

## 常见使用流程

### 1. 准备项目

如果用户还没有项目，先用 `vefaas init` 选择模板并生成本地工程；如果已经有本地项目，直接在项目目录运行 `vefaas inspect` 让 CLI 检测框架、构建命令、输出目录、启动命令和端口。

自动检测不符合项目实际时，再通过部署参数或 `vefaas config settings` 显式指定 build command、output path、start command、port。不要在没有检查项目结构和 `inspect` 结果的情况下猜构建配置。

### 2. 创建或绑定应用

首次把项目发布成应用时，需要创建或绑定 Application。新建应用通常需要一个可用的 APIG gateway name，因为应用需要访问入口；可以用 `vefaas gateway list --first` 查找可用 gateway。

如果没有可用 gateway，停止部署并询问用户提供已有 gateway，或提示用户先到控制台创建。不要静默创建或猜测 gateway。

已有应用时，用 `vefaas link` 或 `vefaas deploy --app/--appId` 绑定到当前目录。涉及写操作时优先使用 application ID；只有名称时先消歧。

### 3. 首次部署前配置环境变量

如果应用启动依赖数据库连接串、API key、模型服务 token 等环境变量，先完成 link，再用 `vefaas env` 设置或导入环境变量，最后再部署。

不要把 secret value 明文回显给用户。导入 `.env.production` 这类文件前，先确认用户确实希望把这些值写入线上环境。

### 4. 部署应用

`vefaas deploy` 会基于本地项目执行构建/打包、上传代码、更新底层函数，并触发应用发布流程。首次部署可通过 `--newApp` 创建应用；后续迭代通常在已 link 的项目目录直接部署。

静态站点会通过生成的 Caddyfile 提供服务。如果输出目录不正确，优先修正 output path；用户明确要求查看或生成 Caddyfile 时，再使用 `vefaas generateCaddy`。

### 5. 查看访问 URL

部署成功后，用 `vefaas domains` 查看应用访问 URL。若访问 URL 缺失或不可用，优先检查：

1. 应用是否部署成功。
2. APIG 触发器是否创建或关联成功。
3. gateway name / gateway 实例是否正确。
4. 当前登录凭据是否具备 APIG 相关权限。

SSO 登录权限不足导致 APIG 操作失败时，引导用户切换 AK/SK 登录并给出 https://console.volcengine.com/iam/keymanage，或自行前往 Web 控制台操作。

### 6. 后续迭代与配置更新

本地代码变更后，一般继续使用 `vefaas deploy` 发布新版本。构建命令、启动命令、端口、资源规格和环境变量变化时，先更新配置，再部署。

如果当前目录已有 `.vefaas/config.json`，也要用 `vefaas config list` 确认 active target 和绑定的应用信息；不要仅凭本地配置文件存在就默认目标正确。

### 7. 排障顺序

应用部署或访问失败时，按下面顺序排查：

1. `vefaas inspect`：确认本地框架检测、构建命令、输出目录、启动命令和端口。
2. `vefaas config list`：确认当前目录绑定的 application ID 和底层 function ID。
3. `vefaas doctor`：检查登录、项目配置、OpenAPI 连通性和应用/函数资源状态。
4. `vefaas domains`：确认访问 URL 和触发器信息。
5. 如服务启动或请求异常，再查看底层函数实例与日志。

涉及删除、覆盖环境变量、修改生产构建配置或重新绑定应用时，先确认应用 ID、目标环境和用户意图。

## 应用查询与管理

应用已经存在时，不一定需要回到本地项目目录。应用维度的只读查询优先用 `vefaas app`：

```bash
vefaas app list -o table
vefaas app info --id <app-id> -o json
vefaas app release --id <app-id> -o table
vefaas app revisions --id <app-id> -o table
vefaas app logs --id <app-id>
```

`overview`、`resource` 是 Console/账号维度查询能力，不属于单个 Application 的生命周期；需要这些能力时读 [CLI 与版本](vefaas-cli.md) 的 Console 视角查询。

### 删除应用

删除应用是高风险操作，不能直接把 `--yes` 当成所有风险的确认。先做前置检查：

```bash
vefaas app delete --id <app-id> --check -o json
```

检查会提示应用是否正在部署/删除、是否存在沙箱实例、Ark 触发器、Coze Terraform Stack、Computer Use Agent ECS，以及 APIG/NAT/EIP 等共享或可能持续计费资源。

处理规则：

1. 先向用户展示应用 ID 和检查结果摘要，再决定是否删除。
2. 如果检查发现 APIG/NAT/EIP 等共享或可能持续计费资源，非交互删除必须显式加 `--ack-shared-resources`。
3. 只有用户明确接受跳过前置阻塞时，才使用 `--force --yes`；此时要说明关联资源可能不会被自动清理。
4. 如果只是想验证能否删除，停在 `--check -o json`，不要继续执行真实删除。
