# CLI 与版本

## 安装或升级

```bash
npm i -g @volcengine/vefaas-cli@latest
vefaas --version
```

## 版本规则

- 推荐同时执行 `vefaas update --check` 检查可用更新；如果当前版本落后，提示用户升级后再继续。
- 升级 CLI 后，建议同步更新本 skill：`npx -y skills add vefaas-dev/skills -g -y`。
- 如果 CLI 版本更旧，先升级，不要尝试兼容旧命令。
- 如果缺少 `app`、`overview`、`resource`、`whoami` 等命令，先升级 CLI，并同步更新本 skill。
- 命令或 flag 不确定时，以当前 `vefaas --help` / `vefaas <command> --help` 为准。

## 资源模型

处理用户问题前，先判断用户说的是函数、应用、沙箱应用，还是沙箱实例。函数是 veFaaS（函数服务）的核心模型；应用和沙箱都建立在函数模型之上，但面向的用户场景不同。不要把这些资源的 ID 混用。

| 用户场景 | 主要资源 | 适合使用 |
| --- | --- | --- |
| 管理一段可运行代码或镜像本身，例如拉取代码、更新配置、查看版本和实例 | 函数 | `vefaas function <command>` 或 `vefaas fn <command>`，以及 `vefaas pull/push/deploy --funcId` |
| 部署一个网站、HTTP 服务、Demo 或完整 Serverless 应用，并希望方便发布和访问 | 应用 | `vefaas init`、`vefaas link`、`vefaas deploy`、`vefaas domains`、`vefaas env`、`vefaas config` |
| 创建一类可秒级拉起的云端隔离运行环境，例如代码沙箱、模型评测环境 | 沙箱应用 | `vefaas sandbox create/info/list/update/delete` |
| 为某次任务创建、暂停、恢复、关闭一个具体运行环境，或调整它的过期时间 | 沙箱实例 | `vefaas sandbox instance create/list/info/pause/resume/kill/timeout` |

### 应用、函数、沙箱的关系

```text
函数 Function（veFaaS 核心资源）
  ├─ Revision：函数配置和代码/镜像的版本快照
  ├─ Instance：按流量和策略动态扩缩容出来的运行实例
  └─ 策略：资源规格、并发、超时、预留实例、定时/弹性扩缩容等

应用 Application
  └─ 关联一个底层函数 Function
      ├─ 整体版本管理
      ├─ APIG 触发器和访问入口关联
      └─ Git 仓库自动触发部署等应用级编排逻辑

独立函数 Function
  └─ 不一定属于应用；可以直接作为函数服务的计算单元管理和发布

沙箱应用 Sandbox application
  └─ 一种特殊/定制的函数，Function、Revision、Instance 模型与函数类似
      ├─ 必须基于已预热镜像创建，以支持秒级拉起实例
      └─ 沙箱实例 Sandbox instance
          ├─ 需要主动创建，不是按请求自动扩出来
          ├─ 多个实例可以并行存在，彼此隔离
          └─ 支持主动 pause/resume/kill 和调整过期时间
```

- **函数**是 veFaaS 的核心资源，承载代码或镜像、运行时、启动命令、端口、环境变量、CPU/内存、并发、超时、版本发布、实例和日志。函数实例由平台根据请求流量和配置策略动态扩缩容，也可以配置预留实例、定时/弹性扩缩容等策略。用户只想操作函数本身时，优先走 `vefaas fn` 或函数相关工作流。
- **应用**是在函数基础上编排了一系列应用级逻辑后包装成的产品，主要包括整体版本管理、APIG 触发器关联、Git 仓库自动触发部署等，使用户可以方便快捷地发布并访问应用。CLI 创建应用时会先创建底层函数，再创建应用并把应用关联到该函数；本地配置里应用 ID 和底层函数 ID 是两个字段。
- **沙箱应用**是一种特殊/定制的函数，Function、Revision、Instance 模型与普通函数很类似，但必须基于已预热镜像创建，以达到秒级拉起实例的效果。它主要面向代码沙箱、模型评测等需要独立云端运行环境的场景。
- **沙箱实例**是从沙箱应用主动创建出来的具体运行实体，不是由请求流量自动扩缩容出来的普通函数实例。创建、暂停、恢复、关闭、设置过期时间等动作都需要先确定沙箱应用 ID，再指定实例 ID 或实例名。
- 沙箱应用下的多个实例通常共享访问域名；访问特定实例时，可使用 `x-faas-instance-name` 请求头或 `faasInstanceName` 查询参数定位实例。

### ID 使用规则

- 应用场景里，`application.id` 是应用 ID，`application.function_id` 才是底层函数 ID。
- 函数场景里，`function.id` 是函数 ID。
- 沙箱场景里，`sandbox.id` 是沙箱应用 ID；实例命令里的 `--instance` 才是沙箱实例标识。
- 本地 `vefaas` 配置的 active target 可能是 `application`、`function`、`sandbox` 或 `local`。写入配置、部署或排障前，优先用 `vefaas config list` / `vefaas doctor` 确认当前绑定对象。
- 如果用户只给了名称、URL 或报错信息，不要猜 ID；先用 list/info/inspect/openapi 查询，再执行修改、删除或发布类操作。

## 顶层能力

```bash
vefaas function <command>        # alias: fn
vefaas application <command>     # alias: app
vefaas sandbox <command>
vefaas gateway <command>
vefaas resource <command>        # alias: res
vefaas overview
vefaas deploy
vefaas pull
vefaas push
vefaas env <action>
vefaas init
vefaas link
vefaas login
vefaas logout
vefaas whoami
vefaas api [action]
vefaas config [action]
vefaas domains
vefaas inspect
vefaas doctor
vefaas generateCaddy
vefaas update
vefaas completion <command>
```

## Console 视角查询

以下命令不是单个 Application 的生命周期操作，而是偏 Console/账号维度的只读查询：

```bash
vefaas overview
vefaas resource list
```

- `overview` 适合快速查看控制台概览类数据。
- `resource summary/list` 适合查询资源分配和使用情况；`resource` 也可写成 `res`，裸 `vefaas res` 默认展示 summary。
