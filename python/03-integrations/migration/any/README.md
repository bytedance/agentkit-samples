# Any 通用迁移 AgentKit Runtime 示例

## 概述

本项目演示如何通过 `--framework any`，将尚未显式适配、结构不固定，或需要自动化迁移分析的 Python agent 项目迁移为可部署到 AgentKit Runtime 的 VeADK 工程。

AgentKit Runtime 原生支持 LangChain、LangGraph、Strands、Google ADK，以及基于 Bedrock AgentCore Runtime 构建的项目。对于暂未显式适配的 Python agent 项目，可以使用 `agentkit migrate --framework any create` 将源项目提交给远端 Codex Sandbox，由沙箱分析项目结构并生成 AgentKit Runtime 可运行的工程。

本示例使用一个 Strands 旅行规划 agent 作为输入。这里使用 `--framework any`，目的是展示通用迁移能力如何自动理解项目结构，而不是要求用户手动声明具体框架。

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
└── any_input/
    └── agent.py       # 原生 Strands 旅行规划 agent
```

`agentkit migrate` 执行后会在输入目录下记录本地迁移任务，并将最终工程写入 `--output` 指定目录。生成文件不需要提前提交到样例源码中。

## 本地运行

### 依赖安装

由于迁移的实际执行在云端的codex沙箱，在执行migrate命令的过程中，您并不需要安装特定的python环境。


### 环境准备

迁移任务需要准备 AgentKit 账号凭证、目标应用模型配置，以及远端 Codex Sandbox 使用的模型 key。

可以复制 `.env.example` 为 `.env`，并在 `.env` 或当前 shell 中填写需要的环境变量。

火山引擎国内版：

```text
VOLCENGINE_ACCESS_KEY=<access-key>
VOLCENGINE_SECRET_KEY=<secret-key>

MODEL_AGENT_NAME=<model-name>
MODEL_AGENT_PROVIDER=openai
MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
MODEL_AGENT_API_KEY=<api-key>

AGENTKIT_MIGRATE_MODEL_API_KEY=<codex-model-api-key>
```

BytePlus 海外版 AgentKit：

```text
BYTEPLUS_ACCESS_KEY=<access-key>
BYTEPLUS_SECRET_KEY=<secret-key>
CLOUD_PROVIDER=byteplus
BYTEPLUS_REGION=ap-southeast-1

MODEL_AGENT_NAME=<model-name>
MODEL_AGENT_PROVIDER=openai
MODEL_AGENT_API_BASE=https://ark.ap-southeast.bytepluses.com/api/v3/
MODEL_AGENT_API_KEY=<api-key>

AGENTKIT_MIGRATE_MODEL_API_KEY=<codex-model-api-key>
```

`MODEL_AGENT_API_KEY` 用于迁移后项目运行时调用业务模型，`AGENTKIT_MIGRATE_MODEL_API_KEY` 用于远端 Codex Sandbox 执行迁移分析。执行迁移命令前，请确保这些变量已经在当前 shell 中生效。

### 创建迁移任务

`create` 会真实发起远端迁移任务。确认环境变量和输入目录后执行：

```bash
cd <project_dir>/any/any_input

agentkit migrate . --framework any create --name any-test --output ../any_output \
  --codex-model <codex_model> \
  --codex-api-key-env AGENTKIT_MIGRATE_MODEL_API_KEY \
  --model-id <model_name> \
  --model-base-url https://ark.cn-beijing.volces.com/api/v3 \
  --model-api-key-env MODEL_AGENT_API_KEY
```

该命令会把 `any_input/` 作为源项目提交给迁移任务，并将最终产物写入 `../any_output`。

## 查询和下载结果

查询任务状态并下载终态产物：

```bash
agentkit migrate . --framework any status --job-id <job_id>
```

也可以使用位置参数形式：

```bash
agentkit migrate . --framework any status <job_id>
```

查看本地迁移任务记录：

```bash
agentkit migrate . --framework any list
```

## AgentKit 部署

迁移完成后进入输出目录，确认 `.agentkit/agentkit.yaml`，然后执行：

```bash
agentkit deploy
```

部署环境中继续使用上面的 AgentKit 账号凭证和模型环境变量。

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
- `list`：查看本地 `.agentkit/migrate/jobs` 记录。
- `--codex-model`：指定远端 Codex Sandbox 使用的模型。
- `--codex-api-key-env`：指定远端 Codex Sandbox 读取模型 key 的环境变量名。
- `--model-id`：指定迁移后项目运行时使用的业务模型。
- `--model-base-url`：指定业务模型的 OpenAI-compatible 接入点。
- `--model-api-key-env`：指定业务模型 key 的环境变量名；不写时默认使用 `MODEL_AGENT_API_KEY`。

## 常见问题

- 为什么示例源项目是 Strands，却使用 `--framework any`？

  本示例用于展示通用迁移链路。已知是 Strands 项目时，也可以参考 `migration/strands` 使用框架专项迁移；当项目结构不固定、入口不明确，或希望由 Codex Sandbox 自动分析时，可以使用 `--framework any`。

- 迁移命令会改写 `any_input/agent.py` 吗？

  不会。迁移任务会把源项目作为输入上传分析，并将生成的 AgentKit Runtime 工程写入 `--output` 指定目录。

## 代码许可

本工程遵循 Apache 2.0 License。
