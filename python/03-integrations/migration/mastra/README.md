# Mastra 迁移 AgentKit Runtime 示例

## 概述

本示例展示如何通过 AgentKit Migration 调用远端 Codex Sandbox，将基于 Mastra 开发的项目迁移为可部署至 AgentKit Runtime 的 VeADK 工程。

Mastra 以 TypeScript 为主要开发语言，其 Agent 基于 Mastra 提供的 @mastra/core/agent 模块进行定义与实现。在大多数 Mastra 项目中，与 Agent 相关的核心逻辑，包括 Agent 定义、Tools 及相关配置等，通常集中在 src/mastra 目录下。

因此，对于大多数结构较为标准的 Mastra 项目，可以直接将 src/mastra 目录作为agentkit migrate的输入，由 codex sandbox 分析其中的 Agent 语义与工具定义，就可以将其迁移为对应的 VeADK 工程。

## 核心功能

- 将 Mastra 项目中的 `src/mastra` 内容提交给Agentkit Codex Sandbox 进行迁移。
- 将简单 Mastra agent + tools 项目转换为 VeADK / AgentKit Runtime 工程。
- 生成可部署配置和运行代码，迁移完成后可执行 `agentkit release`，发布agent到agentkit runtime当中。

## 原输入

本示例的源输入是一个简单的 Mastra agent + tools 项目，作为agentkit codex sandbox迁移的输入。

## 迁移链路

迁移过程分为四步：

1. 准备 Mastra `src/mastra` 内容作为输入。
2. 执行 `agentkit migrate any_input --framework any create` 创建迁移任务。
3. 远端 Codex Sandbox 分析 Mastra agent、tools 和注册关系。
4. 生成 VeADK / AgentKit Runtime 工程，包含 `.agentkit/agentkit.yaml`、运行代码和其他迁移产物。

## 目录结构说明

| 路径 | 说明 |
| --- | --- |
| `.env.example` | 环境变量示例 |
| `README.md` | 中文说明文档 |
| `README_EN.md` | 英文说明文档 |
| `any_input/mastra/index.ts` | Mastra 注册入口 |
| `any_input/mastra/agents/agent.ts` | Mastra agent 定义 |
| `any_input/mastra/tools/beijing-travel-search.ts` | 已注册的北京旅游 mock 搜索工具 |
| `any_input/mastra/tools/schedule-tools.ts` | 未注册的示例工具代码 |
| `any_output/` | 迁移完成后写入的输出目录，与 `any_input/` 同级 |

以下命令均在 `mastra/` 目录下执行。`any_input/` 是源项目输入目录；`--output ../any_output` 以 `any_input/` 为基准解析，迁移产物会写入与 `any_input/` 同级的 `any_output/` 目录。

## 发起远端迁移

### 检查 AgentKit CLI 版本

请先确认本机安装的是 TypeScript 版本的 AgentKit CLI，且版本不低于 `0.51.1`：

```bash
agentkit -v
```

或者

```bash
ak -v
```

如未安装，或版本低于 `0.51.1`，可以使用以下命令安装 TypeScript 版本 AgentKit CLI：

```bash
curl https://agentkit-cli.tos-cn-beijing.volces.com/install.sh | sh
```

> 迁移命令建议使用 TypeScript AgentKit CLI 的 `ak` 入口，以避免 Python `uv` 环境或 `agentkit-python-sdk` 带来的同名 `agentkit` 命令冲突。`ak` 由安装脚本自动配置，无需额外操作。

### 环境准备

在 `mastra/` 目录下复制 `.env.example` 为 `.env`，并在 `.env` 中填写迁移和部署需要的环境变量。

AgentKit CLI 在运行前会自动加载当前执行目录下的 `.env`，不需要手动执行 `source .env`。因此可以直接将环境变量写入 `.env` 中，避免每次手动导入环境变量。其中，`CODEX_MIGRATE_MODEL_API_KEY` 用于远端 Codex Sandbox 迁移任务，`MODEL_AGENT_API_KEY` 用于迁移后应用运行时调用模型。

注意：`--codex-api-key-env` 和 `--model-api-key-env` 传的是环境变量 key 名，CLI 会从 `.env` 中读取对应的真实 key；`--codex-model`、`--model-id`、`--model-base-url` 参数则需要填写实际值。

火山引擎：

```bash
VOLCENGINE_ACCESS_KEY=""
VOLCENGINE_SECRET_KEY=""

CODEX_MODEL_AGENT_NAME=""
CODEX_MIGRATE_MODEL_API_KEY=""

MODEL_AGENT_NAME=""
MODEL_AGENT_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
MODEL_AGENT_API_KEY=""
```

BytePlus 平台：

如果使用 BytePlus 平台，需要填写 BytePlus 的 AK/SK 和模型接入配置。使用 BytePlus 时，在 `.env` 中将火山引擎账号变量替换为 `BYTEPLUS_ACCESS_KEY` / `BYTEPLUS_SECRET_KEY`，并设置 `CLOUD_PROVIDER=byteplus` 和 `BYTEPLUS_REGION`。

```bash
BYTEPLUS_ACCESS_KEY=""
BYTEPLUS_SECRET_KEY=""
CLOUD_PROVIDER=byteplus
BYTEPLUS_REGION=ap-southeast-1

CODEX_MODEL_AGENT_NAME=""
CODEX_MIGRATE_MODEL_API_KEY=""

MODEL_AGENT_NAME=""
MODEL_AGENT_API_BASE=""
MODEL_AGENT_API_KEY=""
```

### 创建迁移任务

`create` 会把 `any_input/` 提交到远端 Codex Sandbox 执行迁移。`--output ../any_output` 以 `any_input/` 为基准解析，最终产物会写入 `mastra/any_output/`。

```bash
cd <project_dir>/mastra

agentkit migrate any_input --framework any create --name mastra-test --output ../any_output \
  --codex-model <codex模型名> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK模型名> \
  --model-base-url <VeADK依赖的模型base_url> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

等价的 `ak` 命令：

```bash
cd <project_dir>/mastra

ak migrate any_input --framework any create --name mastra-test --output ../any_output \
  --codex-model <codex模型名> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK模型名> \
  --model-base-url <VeADK依赖的模型base_url> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

迁移完成后，`any_output/` 会包含完整的 VeADK / AgentKit Runtime 工程，可进入该目录执行 `agentkit release`。

## 查询和下载结果

查询任务状态并下载终态产物：

```bash
agentkit migrate any_input --framework any status --job-id <job_id>
```

等价的 `ak` 命令：

```bash
ak migrate any_input --framework any status --job-id <job_id>
```

也可以使用位置参数形式：

```bash
agentkit migrate any_input --framework any status <job_id>
```

等价的 `ak` 命令：

```bash
ak migrate any_input --framework any status <job_id>
```

查看本地迁移任务记录：

```bash
agentkit migrate any_input --framework any list
```

等价的 `ak` 命令：

```bash
ak migrate any_input --framework any list
```

## 可选：VeADK 项目本地调试

在部署到 AgentKit Runtime 之前，您可以先本地调试迁移后的产物，确保可以运行后再部署到 AgentKit Runtime 上。

## AgentKit 部署

迁移完成后进入输出目录，确认 `.agentkit/agentkit.yaml`，然后执行：

```bash
agentkit release
```

等价的 `ak` 命令：

```bash
ak release
```

## 输出结果

迁移完成后，输出目录通常包含：

- 可直接执行 `agentkit release` 的 VeADK / AgentKit Runtime 工程。
- `.agentkit/agentkit.yaml` 部署配置。
- 迁移说明、运行代码和必要的依赖文件。

具体文件以实际迁移产物为准。如果源项目依赖未配置的外部服务，迁移结果会保留可还原的项目结构，并在产物中说明后续需要补齐的配置。

## 示例提示词

- 我想带父母去北京玩 3 天，总预算 3000 元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
- 我想去日本玩 5 天，帮我安排轻松一点的行程。

## 效果展示

运行示例提示词后，Agent 会结合从 Mastra `src/mastra` 中迁移出的 agent 指令和工具逻辑，输出按天拆分的旅行规划。

```text
北京3天旅行规划

以下内容基于内置的北京旅游 mock 静态资料整理，不是实时搜索结果。出行前请自行核验门票、预约、天气、交通和价格信息。
```

## 参数说明

- `--framework any`：使用通用 agentic migration。
- `create`：创建远端迁移任务。
- `status`：查询任务并下载结果。
- `list`：查看本地 `any_input/.agentkit/migrate/jobs/` 记录。
- `--codex-model`：指定远端 Codex Sandbox 使用的模型，传模型名实际值。
- `--codex-api-key-env`：指定远端 Codex Sandbox 读取模型 key 的环境变量名。
- `--model-id`：指定迁移后项目运行时使用的业务模型，传模型名实际值。
- `--model-base-url`：指定业务模型的 OpenAI-compatible 接入点，传 base URL 实际值。
- `--model-api-key-env`：指定业务模型 key 的环境变量名；不写时默认使用 `MODEL_AGENT_API_KEY`。

## 常见问题

- 迁移命令会改写 `any_input/` 吗？

  不会。迁移任务会把源项目作为输入上传分析，并将生成的 AgentKit Runtime 工程写入 `--output` 指定目录。

- 只提供 `src/mastra` 是否足够？

  对本示例这种简单 Mastra agent + tools 项目是足够的。Codex 迁移所需的必要信息已经包含在 `src/mastra` 内容中，包括 agent 定义、注册入口、工具定义、工具 schema、工具执行逻辑以及 agent 与工具的绑定关系。更复杂的 Mastra 项目如果依赖 `src/mastra` 外的共享模块、资产文件或额外运行配置，则需要一并提供对应上下文。

## 代码许可

本工程遵循 Apache 2.0 License。
