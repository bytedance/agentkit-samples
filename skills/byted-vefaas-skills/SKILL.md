---
name: byted-vefaas-skills
description: "火山引擎函数服务：当用户想把本地前端、Node.js、Python、静态站点或 API 服务部署上线，基于模板创建 serverless 应用，把已有项目接入 veFaaS，查看线上访问地址，配置生产环境变量、构建命令、启动命令或端口，发布、回滚、调用和调试线上函数，查看日志、实例状态或资源配置，拉取/推送云端函数代码，创建和管理沙箱实例，排查部署失败、鉴权失败、框架检测错误、网关缺失等问题，需要直接调用 veFaaS OpenAPI 完成高级操作，或初期上手 veFaaS、想了解 veFaaS 概念/能力/选型/计费、在终端查阅官方文档、接入 veFaaS SDK 或 OpenAPI 进行代码开发时使用。"
allowed-tools: Bash(vefaas:*)
---

# vefaas

本 skill 指导您使用 `@volcengine/vefaas-cli` 操作火山引擎 veFaaS，包括应用部署、函数管理、沙箱管理、环境变量、配置、诊断等在火山引擎函数服务控制台能执行的操作以及 OpenAPI 调用。

## 前置要求

**CRITICAL — 执行任何 veFaaS 操作前，MUST 先确认本机 `vefaas` CLI 版本 >= 0.2.7。**

```bash
vefaas --version
vefaas update --check
```

如果命令不存在，或版本低于 `0.2.7`，必须先升级；如果 `vefaas update --check` 发现可更新版本，应提示用户升级后再继续：

```bash
npm i -g @volcengine/vefaas-cli@latest
vefaas --version
```

**文档检索能力（免登录）——** `vefaas doc` 可在终端检索 veFaaS 官方文档，**无需登录、只读、不计费**。这是本 skill 回答 veFaaS 概念/能力/选型/计费/SDK 用法等问题、以及写 SDK/OpenAPI 代码时的**权威知识来源**，详见下文「文档优先（doc-first）协议」。运行 `vefaas doc --help` 确认可用；若不可用，先 `vefaas update` 升级 CLI。

## 适用场景

使用本 skill：

- 用户要把本地项目、网站、API 服务、Node.js 服务、Python 服务或静态站点部署到火山引擎 veFaaS。
- 用户要基于模板创建 serverless 应用，或把已有项目接入 veFaaS。
- 用户要查看控制台概览、线上访问地址、发布记录、日志或资源用量。
- 用户要配置环境变量、调整构建命令、启动命令、端口或资源配置，或删除已有应用。
- 用户要管理线上函数：创建、查看、发布、回滚、调用、日志、实例、任务、扩缩容策略、触发器、依赖、WebShell。
- 用户要拉取云端函数代码、本地修改后推送或重新部署。
- 用户要管理沙箱应用、沙箱实例、沙箱镜像、沙箱日志、沙箱 WebShell。
- 用户要排查部署失败、鉴权失败、框架检测错误、网关缺失、配置不一致或 OpenAPI 调用失败。
- 用户明确要调用 veFaaS OpenAPI action，或高阶命令无法覆盖目标操作。
- 用户第一次接触 veFaaS、不清楚它是什么或如何上手，需要 landing 引导（无需先登录即可开始）。
- 用户询问 veFaaS 的概念、能力边界、资源选型、计费、限额、触发器等问题，需要基于官方文档准确回答。
- 用户要在自己的代码里接入 veFaaS SDK（Go/Python/Node）或调用 OpenAPI，需要参照官方示例辅助开发。

## 资源心智模型

- 函数是 veFaaS（函数服务）的核心资源，承载代码/镜像、版本、实例、日志、资源规格和扩缩容策略；函数实例通常由平台按流量和策略动态扩缩容。
- 应用是在函数基础上编排应用级逻辑后的产品形态，包含整体版本管理、APIG 触发器关联、Git 仓库自动触发部署等，用于让用户更方便地发布并访问应用。
- 沙箱是一种特殊/定制的函数，Function、Revision、Instance 模型与函数类似，但必须基于已预热镜像创建，适合代码沙箱、模型评测等秒级拉起隔离环境的场景；沙箱实例需要主动创建，并支持暂停、恢复、关闭和调整过期时间。
- 需要更细的资源关系、ID 使用规则或 CLI target 映射时，读取 [CLI 与版本](references/vefaas-cli.md)。

## CRITICAL 工作流分流

**CRITICAL — 先判断用户意图是「知识类」还是「执行类」，再分流：**

- **知识类**（问概念/能力/选型/计费/限额；第一次用、要 landing 上手引导；要写 SDK/OpenAPI 集成代码）→ 走「文档优先（doc-first）工作流」：**先用 `vefaas doc` 检索官方文档，基于文档回答或写代码，通常无需登录**。继续前 MUST 读取 [文档检索与 doc-first](references/vefaas-docs.md)。
- **执行类**（部署、发布、回滚、调用、管理函数/应用/沙箱/网关等真实资源操作）→ 走下面对应的执行工作流。
- **混合类**（如“帮我部署这个项目，顺便讲下计费”）→ 先用 doc-first 答疑，再走执行工作流。

下面是执行类工作流的分流规则：

**CRITICAL — 用户说“部署项目 / 网站上线 / API 上线 / serverless 应用 / 查看访问地址”时，默认走应用工作流，不要直接创建函数。**

应用工作流使用 `vefaas init`、`vefaas inspect`、`vefaas link`、`vefaas deploy`、`vefaas domains`、`vefaas env`、`vefaas config`、`vefaas app`、`vefaas overview`、`vefaas resource`。继续前 MUST 读取 [应用工作流](references/vefaas-application.md)。

**CRITICAL — 只有用户给出已有函数 ID/name，或明确说“函数 / function / fn / 拉取函数代码 / 发布函数 / 回滚函数 / 函数日志”时，才走函数工作流。**

函数工作流使用 `vefaas fn ...`、`vefaas pull`、`vefaas push`、`vefaas deploy --funcId`。继续前 MUST 读取 [函数管理](references/vefaas-function.md)。

**CRITICAL — 用户说“沙箱 / sandbox / 沙箱实例 / 临时实例 / 实例暂停恢复 kill / 沙箱镜像”时，走沙箱工作流。**

沙箱工作流必须区分 sandbox application 与 sandbox instance；application ID 和 instance name 不能混用。继续前 MUST 读取 [沙箱管理](references/vefaas-sandbox.md)。

**CRITICAL — 高阶命令能完成任务时，不要直接使用 `vefaas api`。**

只有在高阶命令缺失、用户明确要求 OpenAPI、或需要底层 action 字段时，才使用 OpenAPI 工作流。继续前 MUST 读取 [OpenAPI 调用](references/vefaas-openapi.md)，并先执行 `vefaas api <Action> --help` 查看参数结构。

## 必读 Reference 协议

执行对应任务前，MUST 读取对应 reference；不要只凭本文件的速查命令执行复杂操作。

| 场景 | 必读文件 |
|---|---|
| 答疑、landing 引导、查官方文档、写 SDK/OpenAPI 集成代码 | [文档检索与 doc-first](references/vefaas-docs.md) |
| 安装、升级、确认 CLI 版本 | [CLI 与版本](references/vefaas-cli.md) |
| 登录、检查凭据、恢复鉴权 | [认证与凭据](references/vefaas-auth.md) |
| 初始化模板、部署应用、link、inspect、domains、应用 env/config | [应用工作流](references/vefaas-application.md) |
| 管理函数、代码、发布、回滚、日志、调用、配置、扩缩容 | [函数管理](references/vefaas-function.md) |
| 函数 APIG 触发器、沙箱网关路由配置、APIG route 绑定与编辑 | [触发器与 APIG Route](references/vefaas-trigger.md) |
| 管理 sandbox application / instance | [沙箱管理](references/vefaas-sandbox.md) |
| 直接调用 veFaaS OpenAPI | [OpenAPI 调用](references/vefaas-openapi.md) |
| 排查失败、诊断环境 | [故障排查](references/vefaas-troubleshooting.md) |

## 全局执行规则

- 非交互式 AI/CI 场景中，目标明确时优先加 `--yes`。
- 需要解析输出时，优先使用 `--output json`，再配合 `--jq`、`--fields`、`--limit`。
- 不确定命令或 flag 时，先运行 `vefaas <command> --help`，不要猜参数。
- 遇到凭据、项目配置、本地环境或 OpenAPI 连通性问题时，优先执行 `vefaas doctor`。
- `--debug` 仅用于诊断；debug 输出和 `~/.vefaas/logs/` 可能包含敏感请求/响应信息。
- 不要把 Access Key ID、Secret Access Key、session token、OAuth/OIDC token、数据库连接串、`.env` value 明文回显给用户。
- `vefaas doc` 系列只读、免登录、不计费，可自由多次调用，不受下文「高风险操作协议」约束。agent 自用文档时一律加 `-o json`，读 `data.markdown`（正文）或 `data.results[]`（搜索结果）；仅当要把文档渲染给人看时才用默认 text 模式。

## 文档优先（doc-first）协议

涉及 veFaaS 的概念、能力、选型、计费、限额、SDK 用法、OpenAPI 参数时，MUST **先用 `vefaas doc` 检索官方文档，再作答或写代码；禁止凭记忆直接回答这些具体事实**。

1. 高频主题用内置别名直达：`intro`（产品介绍）、`quickstart`（快速入门）、`cli`、`sdk`（SDK 概览）、`api`。SDK 各语言用子命令 `vefaas doc sdk go|python|node -o json`。
2. 长尾问题（计费、限额、触发器、网关、某具体功能）先 `vefaas doc search <关键词> -o json`，从 `data.results[]` 按 `title` + `path`（面包屑）挑最匹配的**叶子文档**，取其 `documentId`，再 `vefaas doc --id <id> -o json` 读 `data.markdown`。
3. 答疑：答案不得超出 `data.markdown`；计费/限额/配额必须引用文档原文数值；回答末尾附出处 `data.url` 与更新时间 `data.updatedTime`。
4. 写 SDK/OpenAPI 代码：先取官方示例（`vefaas doc sdk go|python|node -o json`）作骨架；用 `vefaas doc sdk methods <Action> -o json` 查该 Action 的请求字段（type + 说明 + 嵌套），可加 `--lang` 拿请求示例。禁止凭记忆生成 SDK 调用。
5. `vefaas doc --id` 命中目录节点会报 not-found（目录节点无正文）→ 回到 search 结果换一条更深的叶子文档。
6. search 无结果时用 `vefaas doc tree -o json` 浏览目录；仍找不到则如实说明官方文档未覆盖，不要编造。

完整的三类场景工作流（landing / 答疑 / SDK 接入）见 [文档检索与 doc-first](references/vefaas-docs.md)。

## 高风险操作协议

以下操作会影响线上行为或销毁资源，执行前必须确认目标资源和用户意图：

- 删除应用、删除函数、删除沙箱应用、删除沙箱镜像。
- kill / pause / resume sandbox instance。
- 函数或沙箱 rollback。
- 修改生产环境触发器等。

处理规则：

1. 先展示将要操作的资源标识（app/function/sandbox ID 或名称）和动作。
2. 如果目标不唯一或来源只是用户口述名称，先 list/info 消歧。
3. 用户明确确认后再执行；不要静默添加 `--yes` 绕过确认。
4. 用户拒绝或目标不清楚时停止，不要自行猜测替代目标。

**应用删除特殊规则：** 删除 veFaaS Application 前先执行 `vefaas app delete --id <app-id> --check -o json` 做前置检查。若检查发现 APIG/NAT/EIP 等共享或可能持续计费资源，非交互场景必须显式传 `--ack-shared-resources`；不要用全局 `--yes` 代替这类风险确认。只有用户明确接受跳过前置阻塞时，才使用 `--force --yes`，并说明关联资源可能不会被自动清理。

## 目标消歧规则

- App name、function name、sandbox name 可能不唯一；涉及写操作时，优先使用 ID。
- 只有名称没有 ID 时，先用 `list` / `info` / `config list` / `config pull` 获取真实资源信息。
- 新应用部署需要 gateway name；先执行 `vefaas gateway list --first`。如果没有返回，停止并询问用户提供已有网关或先创建网关。
- 当前目录存在 `.vefaas/config.json` 时，不代表一定是用户想操作的目标；涉及线上写操作前先 `vefaas config list` 确认。
- sandbox application ID 与 sandbox instance name 不可互换；实例操作前先 `vefaas sandbox instance list --id <sandbox-application-id>`。

