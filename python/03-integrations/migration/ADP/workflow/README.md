# ADP Workflow 导出物迁移至 AgentKit Runtime 示例

## 概述

本示例演示如何将 ADP Workflow 导出的应用包迁移为可部署到 AgentKit Runtime 的 VeADK 工程。

ADP Workflow 导出包不是可直接发布到 AgentKit Runtime 的 Python 工程。其应用信息、提示词、节点编排和运行配置主要保存在平台导出的 JSON 文件中。对于这类低代码平台生成的 Workflow 项目，可结合 AgentKit Migration 命令与 AgentKit Codex Sandbox 的能力完成自动化迁移：使用 `agentkit migrate any_input --framework any create` 创建迁移任务并提交导出包，由远端 Codex Sandbox 分析应用配置、工作流结构和可见行为，并生成可部署到 AgentKit Runtime 的 VeADK 工程。

本示例输入是一个酒店预定类 ADP Workflow 应用。源应用采用 `START -> LLM -> ANSWER -> END` 的单工作流链路，核心行为是根据用户需求生成酒店预定规划，并在北京酒店场景下推荐「北京饭店」。迁移后的输出是一个经过codex转化过的VeADK项目。

本文档将引导你完成导出包准备、远端迁移任务创建、结果查询下载、迁移产物检查，以及通过 `agentkit release` 发布到 AgentKit Runtime。

## 核心功能

本示例覆盖从 ADP Workflow 导出包到 AgentKit Runtime 工程的完整迁移路径：

- 读取 ADP Workflow 导出包中的应用元信息、工作流结构、提示词和可见行为。
- 通过远端 Codex Sandbox 将单工作流应用转换为 VeADK / AgentKit Runtime 工程。
- 生成可部署配置、运行代码、迁移报告和评测样例，并支持继续执行 `agentkit release`。
- 对源应用中不存在的外部依赖、工具调用或真实预订能力，在迁移产物中保留能力边界说明，不伪造外部调用结果。

## 原输入

输入目录是 `any_input/`，其中包含从 ADP 平台导出的 Workflow 应用包。准备方式如下：在 ADP 应用列表中选择目标应用并导出，下载 ZIP 文件后解压，再将解压后的导出目录整体放入 `any_input/`。

本示例中的输入目录为：

```bash
any_input/
├── metadata.json
└── app/
    ├── metadata.json
    ├── app_config/
    │   ├── app_synonyms.json
    │   ├── app_variable.json
    │   ├── base_config.json
    │   └── metadata.json
    └── workflow/
        ├── metadata.json
        ├── workflow_config.json
        └── workflow_example.json
```

源应用大致信息如下：

- 应用名称：`workflow_agent_example`
- Agent 名称：`酒店预定agent`
- 工作流模式：`single_workflow`
- 工作流链路：`START -> LLM -> ANSWER -> END`

## 迁移流程

```text
ADP Workflow 导出 ZIP
    ↓
解压后放入 any_input/
    ↓
agentkit migrate any_input --framework any create
    ↓
远端 Codex Sandbox 分析导出包结构和工作流行为
    ↓
VeADK / AgentKit Runtime 工程
    ├── .agentkit/agentkit.yaml
    ├── assistant/agent.py
    ├── main.py
    ├── migration_metadata.json
    ├── convert_report.md
    └── eval/
```

## 目录结构说明

```bash
workflow/
├── .env.example       # 环境变量示例
├── README.md          # 中文说明文档
├── any_input/         # ADP Workflow 导出包输入目录
```

后续命令均在 `ADP/workflow/` 目录下执行。`any_input/` 是源项目输入目录；`--output ../any_output` 以 `any_input/` 为基准解析，迁移产物会写入与 `any_input/` 同级的 `any_output/` 目录。

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

在 `ADP/workflow/` 目录下复制 `.env.example` 为 `.env`，并在 `.env` 中填写迁移和部署所需的环境变量。

AgentKit CLI 在运行前会自动加载当前执行目录下的 `.env`，不需要手动执行 `source .env`。因此，可以直接将环境变量写入 `.env`，避免每次手动导入。其中，`CODEX_MIGRATE_MODEL_API_KEY` 用于远端 Codex Sandbox 迁移任务，`MODEL_AGENT_API_KEY` 用于迁移后应用运行时调用模型。

注意：`--codex-api-key-env` 和 `--model-api-key-env` 传入的是环境变量 key 名，CLI 会从 `.env` 中读取对应的真实 key；`--codex-model`、`--model-id`、`--model-base-url` 参数需要填写实际值。

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

如果使用 BytePlus 平台，需要填写 BytePlus 的 AK/SK 和模型接入配置。在 `.env` 中将火山引擎账号变量替换为 `BYTEPLUS_ACCESS_KEY` / `BYTEPLUS_SECRET_KEY`，并设置 `CLOUD_PROVIDER=byteplus` 和 `BYTEPLUS_REGION`。

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

`create` 会把 `any_input/` 提交到远端 Codex Sandbox 执行迁移。`--output ../any_output` 以 `any_input/` 为基准解析，最终产物会写入 `ADP/workflow/any_output/`。

```bash
cd <project_dir>/ADP/workflow

agentkit migrate any_input --framework any create --name any-test --output ../any_output \
  --codex-model <codex模型名> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK模型名> \
  --model-base-url <VeADK依赖的模型base_url> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

使用 `ak` 的等价命令：

```bash
cd <project_dir>/ADP/workflow

ak migrate any_input --framework any create --name any-test --output ../any_output \
  --codex-model ep-20260601142014-7hztz \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id ep-20260601142014-7hztz \
  --model-base-url "https://ark.cn-beijing.volces.com/api/v3" \
  --model-api-key-env MODEL_AGENT_API_KEY
```

创建成功后，命令会返回 `job_id`。本示例的实测任务记录保存在 `any_input/.agentkit/migrate/jobs/<job_id>.json`，迁移结果已下载到 `any_output/`。

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

任务成功后，`any_output/convert_report.md` 会记录源应用识别结果、行为分析、生成文件、验证结论和后续部署说明。

## 可选：VeADK 项目本地调试

在部署到 AgentKit Runtime 之前，可以先进入 `any_output/` 查看迁移产物，建议重点检查：

- `assistant/agent.py`：迁移后的 VeADK agent，包含酒店预定专家人设、北京饭店推荐规则和只读边界说明。
- `.agentkit/agentkit.yaml`：AgentKit Runtime 部署配置，包含模型、资源规格、环境变量和 APMPlus 配置。
- `migration_metadata.json`：源应用信息、保留行为、降级行为和评测套件说明。
- `eval/cases.json` 与 `eval/rubric.md`：迁移后行为验证样例与评测标准。

本示例迁移产物已通过 `convert_report.md` 中记录的静态校验，包括 Python 编译、关键文件存在性、`assistant.agent.root_agent` 导入、`main.app` 导入和 AgentKit 配置检查。

## AgentKit 部署

迁移完成后，进入输出目录，确认 `.agentkit/agentkit.yaml` 配置无误，然后执行：

```bash
cd any_output
agentkit release
```

等价的 `ak` 命令：

```bash
cd any_output
ak release
```

实测流程中，`release` 会构建镜像并发布 Runtime。发布完成后，可以在 AgentKit 控制台进入在线测试页面验证 agent 响应。

## 输出结果

迁移完成后，输出目录通常包含：

- 可直接执行 `agentkit release` 的 VeADK / AgentKit Runtime 工程。
- `.agentkit/agentkit.yaml` 部署配置。
- `assistant/agent.py` 运行代码。
- `convert_report.md` 迁移报告。
- `migration_metadata.json` 迁移元数据。
- `source_behavior_contract.json` 源行为契约。
- `eval/cases.json` 和 `eval/rubric.md` 评测样例。

本示例输出中，源 workflow 被转换为一个名为 `hotel_booking_agent` 的 VeADK agent。它保留酒店预定咨询和北京酒店推荐行为，并在用户要求实际下单、支付或代订时，说明当前只能提供推荐和规划服务。
