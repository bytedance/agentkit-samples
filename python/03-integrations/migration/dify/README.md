# Dify 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将 Dify 导出的 workflow 接入 AgentKit Runtime。

Dify workflow 通常不是一个可以直接运行的 Python 项目。迁移时，`agentkit migrate` 会把 Dify 导出目录提交给远端 Codex Sandbox，由沙箱分析 `workflow.yml`、可选的 `node_config.yml` 和工作流结构，并生成可部署到 AgentKit Runtime 的 VeADK 工程。

本示例使用一个 Dify advanced-chat 应用「专属智能客服」作为输入。示例重点展示通用迁移链路，实际业务场景可以替换为其他 Dify 导出的 workflow。

## 核心功能

- 将 Dify workflow 转换为可部署的 VeADK / AgentKit Runtime 工程。
- 支持随 workflow 一起上传 `node_config.yml`，补充节点运行配置。
- 生成部署配置、迁移报告、迁移计划和评测用例。
- 对未配置的知识库、插件、HTTP 服务等外部依赖，在迁移报告中明确说明，不伪造外部调用成功。

## 迁移链路

```text
Dify 导出目录
    ↓
agentkit migrate --framework dify create
    ↓
远端 Codex Sandbox
    ↓
VeADK / AgentKit Runtime 工程
    ├── assistant/agent.py
    ├── assistant/workflow.py
    ├── .agentkit/agentkit.yaml
    ├── convert_report.md
    ├── migration_plan.md
    └── eval/
```

## 目录结构说明

```bash
dify/
├── README.md            # 中文说明文档
├── README_EN.md         # 英文说明文档
├── .env.example         # 环境变量模板，复制为 .env 后填写真实值
├── dify_input/
│   ├── workflow.yml     # Dify 导出的 workflow
│   └── node_config.yml  # 可选的节点运行配置
└── dify_output/         # 迁移完成后写入的输出目录，与 dify_input 同级
```

以下命令均在 `dify/` 目录下执行。`dify_input/` 是 Dify workflow 的输入目录；`--output ../dify_output` 以 `dify_input/` 为基准解析，迁移产物会写入与 `dify_input/` 同级的 `dify_output/` 目录。

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

在 `dify/` 目录下复制 `.env.example` 为 `.env`，并在 `.env` 中填写迁移和部署需要的环境变量。

AgentKit CLI 会读取当前执行目录下的 `.env`，不需要手动执行 `source .env`。您可以直接将环境变量写入 `.env`。其中，`CODEX_MIGRATE_MODEL_API_KEY` 用于远端 Codex Sandbox 迁移任务，`MODEL_AGENT_API_KEY` 用于迁移后应用运行时调用模型。

注意：`--codex-api-key-env` 和 `--model-api-key-env` 传的是环境变量 key 名，CLI 会从 `.env` 中读取对应的真实 key；`--codex-model`、`--model-id`、`--model-base-url` 参数则需要填写实际值。

火山引擎：

```bash
VOLCENGINE_ACCESS_KEY=""
VOLCENGINE_SECRET_KEY=""

CODEX_MODEL_AGENT_NAME=""
CODEX_MIGRATE_MODEL_API_KEY=""

MODEL_AGENT_NAME=""
MODEL_AGENT_API_BASE=""
MODEL_AGENT_API_KEY=""
```

BytePlus 平台：

如果使用 BytePlus 平台，请在 `.env` 中将火山引擎账号变量替换为 `BYTEPLUS_ACCESS_KEY` / `BYTEPLUS_SECRET_KEY`，并设置 `CLOUD_PROVIDER=byteplus` 和 `BYTEPLUS_REGION`。

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

`create` 会把 `dify_input/` 提交到远端 Codex Sandbox 执行迁移。`--output ../dify_output` 以 `dify_input/` 为基准解析，最终产物会写入 `dify/dify_output/`。

```bash
cd <project_dir>/dify

agentkit migrate dify_input --framework dify create --name dify-migrate --output ../dify_output \
  --codex-model <codex模型名> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK模型名> \
  --model-base-url <VeADK依赖的模型base_url> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

等价的 `ak` 命令：

```bash
cd <project_dir>/dify

ak migrate dify_input --framework dify create --name dify-migrate --output ../dify_output \
  --codex-model <codex模型名> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK模型名> \
  --model-base-url <VeADK依赖的模型base_url> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

迁移完成后，`dify_output/` 会包含可部署的 VeADK / AgentKit Runtime 工程。进入该目录后，可以执行 `agentkit release`。

## 查询和下载结果

查询任务状态并下载终态产物：

```bash
agentkit migrate dify_input --framework dify status --job-id <job_id>
```

等价的 `ak` 命令：

```bash
ak migrate dify_input --framework dify status --job-id <job_id>
```

也可以使用位置参数形式：

```bash
agentkit migrate dify_input --framework dify status <job_id>
```

等价的 `ak` 命令：

```bash
ak migrate dify_input --framework dify status <job_id>
```

查看本地迁移任务记录：

```bash
agentkit migrate dify_input --framework dify list
```

等价的 `ak` 命令：

```bash
ak migrate dify_input --framework dify list
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

- 可执行 `agentkit release` 的 VeADK / AgentKit Runtime 工程。
- `.agentkit/agentkit.yaml` 部署配置。
- `convert_report.md` 迁移报告。
- `migration_plan.md` 迁移计划。
- `eval/` 评测用例。

如果源 Dify workflow 依赖未配置的知识库、Dify marketplace 插件或其他外部服务，迁移结果会保留工作流结构，并在报告中说明降级点。

## 常见问题

- `node_config.yml` 必须提供吗？

  不是必须。它用于补充节点运行配置；如果您的 Dify 节点依赖外部配置（例如 RAG、知识库、Memory），可以在 `node_config.yml` 中直接提供，也可以后续在 VeADK 项目中加入这些配置。

- 外部依赖无法还原怎么办？

  迁移不会伪造外部调用成功。未配置的知识库、插件、HTTP 服务等会在迁移报告中说明，后续可以在输出工程中补齐配置。

## 代码许可

本工程遵循 Apache 2.0 License。
