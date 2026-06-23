# 环境变量说明

本项目功能较多（模型、记忆、知识库、可观测、技能执行与文件上传等），因此需要较多环境变量。本文档说明每个变量的用途、示例取值，以及未配置时的行为。

## 使用方式

- **本地运行**：在终端里导出环境变量，或使用你自己的 `.env`/shell 配置方式（请不要提交密钥到仓库）。
- **云端运行**：在 `agentkit.yaml` 的 `runtime_envs` 中配置（同样不要提交真实密钥到公开仓库）。

## 加载优先级（兼容本地调试）

VeADK 会按如下优先级读取配置（优先级由高到低）：

1. 系统环境变量
2. `.env` 文件
3. `config.yaml` 文件

`.env` 的查找通常与**进程启动时的工作目录（cwd）**有关，因此有两种常见放置方式：

- 放在 `agent/.env`（推荐）：配合默认启动命令 `cd agent && python3 agentkit-agent.py`，VeADK 会在当前目录读取 `.env`。
- 放在仓库根目录 `.env`：需要从根目录启动（例如 `python3 agent/agentkit-agent.py`），否则 VeADK 在 `agent/` 下启动时不会自动读取到根目录的 `.env`。

## 最小可用（本地）

以下变量缺失会导致模型无法正常调用：

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `MODEL_AGENT_API_KEY` | 大模型调用的 API Key（VeADK/Agent 会用它访问模型服务） | `MODEL_AGENT_API_KEY="YOUR_API_KEY"` | 模型请求将失败（鉴权失败或无 Key） |

获取方式：在火山引擎控制台创建/查看你的模型服务 API Key，并将其以环境变量或 `.env` 的方式注入（不要提交到仓库）。

## 应用基础信息

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `VEADK_APP_NAME` | 应用名（同时影响记忆/知识库的 app_name 命名空间） | `carselector_unified` | 默认 `carselector_unified` |
| `VEADK_AGENT_NAME` | Agent 名称 | `carselector_unified` | 默认等于 `VEADK_APP_NAME` |
| `VEADK_APP_DESCRIPTION` | 应用描述 | `智能选车助手（Unified）` | 使用内置默认描述 |
| `VEADK_ENABLE_RESPONSES` | 是否开启 responses 相关能力（布尔） | `true` / `false` | 默认 `false` |

## 工具开关（Built-in Tools）

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `VEADK_BUILTIN_TOOLS_ENABLE` | 内置工具白名单（逗号分隔） | `web_search,execute_skills,image_generate` | 为空时：加载代码中可导入的全部内置工具 |

## Prompt / 指令

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `PROMPT_MANAGEMENT_LOCAL_INSTRUCTION_FILE` | 本地指令文件路径（相对路径相对 `agent/`） | `instruction.md` | 默认 `instruction.md` |
| `PROMPT_MANAGEMENT_COZELOOP_PROMPT_KEY` | Cozeloop Prompt Key（启用远端 Prompt 管理） | `carselector_unified_sysprompt` | 为空：不启用 Cozeloop PromptManager（使用本地 instruction） |
| `PROMPT_MANAGEMENT_COZELOOP_WORKSPACE_ID` | Cozeloop Workspace ID | `YOUR_WORKSPACE_ID` | 为空：不启用 Cozeloop PromptManager |
| `PROMPT_MANAGEMENT_COZELOOP_TOKEN` | Cozeloop Token | `REPLACE_ME` | 为空：不启用 Cozeloop PromptManager |
| `PROMPT_MANAGEMENT_COZELOOP_LABEL` | Cozeloop Label（环境/版本标签） | `beta` | 默认 `beta` |

## 会话与记忆（Memory）

短期记忆在本地默认使用 `local`，如果配置了 PostgreSQL 则切换为 `postgresql`；长期记忆与知识库则按需启用。

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `DATABASE_POSTGRESQL_HOST` | PostgreSQL Host（短期记忆启用条件） | `127.0.0.1` | 为空：短期记忆使用本地 `local` 后端 |
| `DATABASE_POSTGRESQL_DATABASE` | PostgreSQL DB 名 | `carselector_mem` | 为空：短期记忆使用本地 `local` 后端 |
| `DATABASE_POSTGRESQL_USER` | PostgreSQL 用户名 | `postgres` | 为空：短期记忆使用本地 `local` 后端 |
| `DATABASE_POSTGRESQL_PASSWORD` | PostgreSQL 密码 | `YOUR_PASSWORD` | 为空：短期记忆使用本地 `local` 后端 |
| `DATABASE_VIKING_MEM_COLLECTION_NAME` | Viking 记忆集合名（长期记忆） | `carselector_shared_memory` | 为空：不启用长期记忆，且不会自动保存会话 |
| `DATABASE_VIKING_COLLECTION_NAME` | Viking 知识库集合名 | `carselector_kb` | 为空：不启用知识库 |
| `DATABASE_VIKING_PROJECT` | Viking Project | `default` | 由后端 SDK 自行处理；为空可能使用默认值 |
| `DATABASE_VIKING_REGION` | Viking Region | `cn-beijing` | 由后端 SDK 自行处理；为空可能使用默认值 |

## 文件上传（TOS）

本项目会在需要生成图片/表格等文件时上传到 TOS 并返回可下载链接（如果未配置则会回退为“无法上传”的错误信息）。

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `DATABASE_TOS_BUCKET` | TOS Bucket 名 | `your-bucket` | 为空：上传功能不可用（会返回缺少 bucket 的错误） |
| `DATABASE_TOS_ENDPOINT` | TOS Endpoint | `tos-cn-beijing.volces.com` | 默认 `tos-cn-beijing.volces.com` |
| `DATABASE_TOS_REGION` | TOS Region | `cn-beijing` | 默认 `cn-beijing` |
| `VOLCENGINE_ACCESS_KEY` | 火山 AK（用于签名上传/下载） | `AKxxx` | 为空：无法初始化 TOS 客户端，上传不可用 |
| `VOLCENGINE_SECRET_KEY` | 火山 SK（用于签名上传/下载） | `xxxx` | 为空：无法初始化 TOS 客户端，上传不可用 |
| `VOLCENGINE_REGION` | 火山 Region | `cn-beijing` | 由后端 SDK 自行处理；为空可能使用默认值 |

## 事件压缩（Events Compaction）

`agentkit-agent.py` 会给 A2A App 配置事件压缩，未配置时使用默认模型与参数。

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `EVENTS_COMPACTION_MODEL` | 用于摘要/压缩事件的模型标识 | `openai/doubao-seed-1-6-lite-251015` | 使用默认值 |
| `EVENTS_COMPACTION_API_BASE` | 事件压缩模型的 API Base | `https://ark.cn-beijing.volces.com/api/v3/` | 使用默认值 |
| `EVENTS_COMPACTION_API_KEY` | 事件压缩模型的 API Key | `YOUR_API_KEY` | 为空：回退使用 `MODEL_AGENT_API_KEY` |
| `EVENTS_COMPACTION_INTERVAL` | 压缩触发间隔（整数） | `3` | 默认 `3` |
| `EVENTS_COMPACTION_OVERLAP_SIZE` | 压缩重叠窗口（整数） | `1` | 默认 `1` |
| `EVENTS_COMPACTION_PROMPT_FILE` | 压缩 prompt 模板文件名/路径（按运行环境约定） | `compaction_prompt_template.txt` | 由运行环境/实现自行处理 |
| `EVENTS_COMPACTION_COZELOOP_PROMPT_KEY` | Cozeloop 下的 compaction prompt key | `carselector_events_compaction_prompt` | 为空：不使用 Cozeloop compaction prompt |
| `EVENTS_COMPACTION_COZELOOP_WORKSPACE_ID` | Cozeloop Workspace ID | `YOUR_WORKSPACE_ID` | 为空：不使用 Cozeloop compaction prompt |
| `EVENTS_COMPACTION_COZELOOP_TOKEN` | Cozeloop Token | `REPLACE_ME` | 为空：不使用 Cozeloop compaction prompt |
| `EVENTS_COMPACTION_COZELOOP_LABEL` | Cozeloop Label | `beta` | 由实现自行处理 |

## 可观测（Observability）

只要对应 endpoint 未配置，就会自动跳过 tracer/exporter 初始化。

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `OBSERVABILITY_OPENTELEMETRY_APMPLUS_ENDPOINT` | APMPlus OTLP Endpoint | `http://apmplus:4317` | 为空：不启用 APMPlus exporter |
| `OBSERVABILITY_OPENTELEMETRY_APMPLUS_API_KEY` | APMPlus API Key | `YOUR_APMPLUS_KEY` | 为空：不启用 APMPlus exporter |
| `OBSERVABILITY_OPENTELEMETRY_APMPLUS_SERVICE_NAME` | APMPlus 服务名 | `carselector_unified` | 由 exporter/实现自行处理 |
| `OBSERVABILITY_OPENTELEMETRY_COZELOOP_ENDPOINT` | Cozeloop OTLP Endpoint | `https://api.coze.cn/.../traces` | 为空：不启用 Cozeloop exporter |
| `OBSERVABILITY_OPENTELEMETRY_COZELOOP_API_KEY` | Cozeloop API Key/Token | `REPLACE_ME` | 为空：不启用 Cozeloop exporter |
| `OBSERVABILITY_OPENTELEMETRY_COZELOOP_SERVICE_NAME` | Cozeloop 服务名 | `YOUR_WORKSPACE_ID` | 由 exporter/实现自行处理 |
| `OBSERVABILITY_OPENTELEMETRY_TLS_ENDPOINT` | TLS OTLP Endpoint | `https://tls.../traces` | 为空：不启用 TLS exporter |
| `OBSERVABILITY_OPENTELEMETRY_TLS_REGION` | TLS Region | `cn-beijing` | 由 exporter/实现自行处理 |

## AgentKit（云端/应用场景）

这些变量主要用于云端运行时的“工具/技能空间”定位与配置；本地运行通常不需要全部配置。

| 变量 | 含义 | 示例 | 为空时行为 |
|---|---|---|---|
| `AGENTKIT_TOOL_ID` | AgentKit 工具 ID | `t_xxx` | 由云端部署平台决定；为空可能导致工具不可用 |
| `AGENTKIT_TOOL_REGION` | AgentKit 工具 Region | `cn-beijing` | 由云端部署平台决定 |
| `SKILL_SPACE_ID` | Skill Space ID | `ss_xxx` | 由云端部署平台决定；为空可能导致 skills 不可用 |

## 安全建议（强烈）

- 不要把任何 `*_API_KEY`、`*_TOKEN`、`*_PASSWORD`、`VOLCENGINE_*` 这类敏感信息提交到仓库。
- 推荐在本地使用环境变量或密钥管理系统（KMS），在 CI/CD 与云端部署通过安全注入方式提供密钥。
