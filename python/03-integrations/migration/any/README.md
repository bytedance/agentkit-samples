# Any 通用迁移 AgentKit Runtime 示例

## 概述

本项目演示如何通过 `--framework any`，将尚未显式适配、结构不固定，或需要自动化迁移分析的 Python agent 项目迁移为可部署到 AgentKit Runtime 的 VeADK 工程。

AgentKit Runtime 原生支持 LangChain、LangGraph、Strands、Google ADK，以及基于 Bedrock AgentCore Runtime 构建的项目。对于暂未显式适配的 Python agent 项目，可以使用 `agentkit migrate --framework any create` 将源项目提交给远端 Codex Sandbox，由沙箱分析项目结构并生成 AgentKit Runtime 可运行的工程。

本示例使用一个 Strands 旅行规划 agent 作为输入。这里使用 `--framework any`，目的是展示通用迁移能力如何自动理解项目结构.

## 核心功能

- 将已有 Python agent 项目目录提交给远端 Codex Sandbox 进行迁移。
- 将源项目转换为 VeADK / AgentKit Runtime 工程。
- 生成可部署配置和运行代码，迁移完成后可继续执行 `agentkit deploy`。
- 对无法自动还原的外部依赖或运行配置，在迁移产物中保留说明，不伪造外部调用成功。

## 原输入

输入目录是 `any_input/`，其中包含一个旅行规划 agent：

- 入口代码：`any_input/agent.py`
- 原生框架：Strands `Agent`
- 本地工具：城市资料检索、预算估算、交通建议
- 模型配置：配置 `MODEL_AGENT_NAME` 和 `MODEL_AGENT_API_KEY` 后调用 OpenAI-compatible 模型；未配置时使用本地 `LocalTravelModel` 方便预检
- 迁移目标：让 Codex Sandbox 自动理解项目结构，并生成 VeADK / AgentKit Runtime 输出工程

## 迁移链路

```text
Python agent 项目
    ↓
agentkit migrate --framework any create
    ↓
远端 Codex Sandbox
    ↓
VeADK / AgentKit Runtime 工程
    ├── .agentkit/agentkit.yaml
    └── 运行代码等迁移产物
```

## 目录结构说明

```bash
any/
├── .env.example       # 环境变量示例
├── README.md          # 中文说明文档
├── README_EN.md       # 英文说明文档
├── requirements.txt   # Python 依赖列表
├── any_input/
│   └── agent.py       # 原生 Strands 旅行规划 agent
└── any_output/        # 迁移完成后写入的输出目录，与 any_input 同级
```

以下命令均在 `any/` 目录下执行。`any_input/` 是源项目输入目录；`--output ../any_output` 以 `any_input/` 为基准解析，迁移产物会写入与 `any_input/` 同级的 `any_output/` 目录。

## 发起远端迁移

### 检查 AgentKit CLI 版本

请先确认本机安装的是 TypeScript 版本的 AgentKit CLI，且版本不低于 `0.50.4`：

```bash
agentkit -v
```

如未安装，或版本低于 `0.50.4`，可以使用以下命令安装 TypeScript 版本 AgentKit CLI：

```bash
curl https://agentkit-cli.tos-cn-beijing.volces.com/install.sh | sh
```

### 环境准备

在 `any/` 目录下复制 `.env.example` 为 `.env`，并在 `.env` 中填写迁移和部署需要的环境变量。

AgentKit CLI 在运行前会自动加载当前执行目录下的 `.env`，不需要手动执行 `source .env`。因此可以直接将环境变量写入 `.env` 中，避免每次手动导入环境变量。其中，`CODEX_MIGRATE_MODEL_API_KEY` 用于远端 Codex Sandbox 迁移任务，`MODEL_AGENT_API_KEY` 用于迁移后应用运行时调用模型。

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

`create` 会把 `any_input/` 提交到远端 Codex Sandbox 执行迁移。`--output ../any_output` 以 `any_input/` 为基准解析，最终产物会写入 `any/any_output/`。

```bash
cd <project_dir>/any

agentkit migrate any_input --framework any create --name any-test --output ../any_output \
  --codex-model <codex模型名> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK模型名> \
  --model-base-url <VeADK依赖的模型base_url> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

迁移完成后，`any_output/` 会包含完整的 VeADK / AgentKit Runtime 工程，可进入该目录执行 `agentkit deploy`。

## 查询和下载结果

查询任务状态并下载终态产物：

```bash
agentkit migrate any_input --framework any status --job-id <job_id>
```

也可以使用位置参数形式：

```bash
agentkit migrate any_input --framework any status <job_id>
```

查看本地迁移任务记录：

```bash
agentkit migrate any_input --framework any list
```

## 可选：VeADK项目本地调试

在部署到AgentKit Runtime之前，您可以先本地调试migration迁移后的产物，确保可以运行后再部署到AgentKit Runtime上。

## AgentKit 部署

迁移完成后进入输出目录，确认 `.agentkit/agentkit.yaml`，然后执行：

```bash
agentkit deploy
```

## 输出结果

迁移完成后，输出目录通常包含：

- 可直接执行 `agentkit deploy` 的 VeADK / AgentKit Runtime 工程。
- `.agentkit/agentkit.yaml` 部署配置。
- 迁移说明、运行代码和必要的依赖文件。

具体文件以实际迁移产物为准。如果源项目依赖未配置的外部服务，迁移结果会保留可还原的项目结构，并在产物中说明后续需要补齐的配置。

## 示例提示词

- 我想带父母去北京玩 3 天，总预算 3000 元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
- 我想去西安玩 2 天，预算 1800 元，喜欢历史遗迹和当地小吃，请安排一个不太累的路线。

## 效果展示

运行示例提示词后，Agent 会结合本地城市资料、预算判断和交通建议，输出按天拆分的旅行规划。

```text
北京3天旅行规划（示例模型输出）

需求摘要：带父母/长辈，结合本地资料、预算和交通建议安排路线。
预算建议：北京3天总预算3000元，人均每日约1000元，预算判断：比较宽松。
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
- 迁移命令会改写 `any_input/agent.py` 吗？

  不会。迁移任务会把源项目作为输入上传分析，并将生成的 AgentKit Runtime 工程写入 `--output` 指定目录。

## 代码许可

本工程遵循 Apache 2.0 License。
