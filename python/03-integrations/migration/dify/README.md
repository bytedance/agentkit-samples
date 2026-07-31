# Dify 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将 Dify 导出的 workflow 迁移为可部署到 AgentKit Runtime 的 VeADK 工程。

Dify workflow 通常没有固定的 Python agent 入口。迁移时，`agentkit migrate` 会将 Dify 导出目录提交给远端 Codex Sandbox，由沙箱分析 `workflow.yml`、可选的 `node_config.yml` 和工作流图结构，并生成 AgentKit Runtime 可运行的工程。

本示例使用一个 Dify advanced-chat 应用「专属智能客服」作为输入。示例重点展示通用迁移链路，实际业务场景可以替换为其他 Dify 导出的 workflow。

## 核心功能

- 将 Dify workflow 转换为 VeADK / AgentKit Runtime 工程。
- 支持随 workflow 一起上传 `node_config.yml`，补充节点运行配置。
- 生成可部署配置、迁移报告、迁移计划和评测用例。
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
├── requirements.txt     # Python 依赖列表
├── dify_input/
│   ├── workflow.yml     # Dify 导出的 workflow
│   └── node_config.yml  # 可选的节点运行配置
└── dify_output/         # 迁移完成后写入的输出目录
```

`agentkit migrate` 执行后会在输入目录下记录本地迁移任务，并将最终工程写入 `--output` 指定目录。

## 本地运行


### 环境准备

迁移任务需要准备 AgentKit 账号凭证、目标应用模型配置，以及远端 Codex Sandbox 使用的模型 key。

使用 cp 复制.env.example到.env，将下面的值写入agentkit.yaml中。
因为迁移的链路需要用到codex sandbox，所以需要提供您账户的AKSK和MODEL的API_KEY。

火山引擎：

```bash
VOLCENGINE_ACCESS_KEY=""
VOLCENGINE_SECRET_KEY=""

MODEL_AGENT_API_KEY=""
AGENTKIT_MIGRATE_MODEL_API_KEY=""
```

BytePlus 海外版：

```bash
BYTEPLUS_ACCESS_KEY=""
BYTEPLUS_SECRET_KEY=""
CLOUD_PROVIDER=byteplus
BYTEPLUS_REGION=ap-southeast-1
MODEL_AGENT_API_KEY=""
AGENTKIT_MIGRATE_MODEL_API_KEY=""
```

### 创建迁移任务

`create` 会真实发起远端迁移任务。确认环境变量和输入目录后执行：

```bash
cd <project_dir>/dify/dify_input

agentkit migrate . --framework dify create --name dify-migrate --output ../dify_output \
  --codex-model <codex_model> \
  --codex-api-key-env AGENTKIT_MIGRATE_MODEL_API_KEY \
  --model-id <model_name> \
  --model-base-url https://ark.cn-beijing.volces.com/api/v3 \
  --model-api-key-env MODEL_AGENT_API_KEY
```

该命令会把当前目录的 Dify workflow 作为源输入，并将最终产物写入 `../dify_output`。

## 查询和下载结果

查询任务状态并下载终态产物：

```bash
agentkit migrate . --framework dify status --job-id <job_id>
```

也可以使用位置参数形式：

```bash
agentkit migrate . --framework dify status <job_id>
```

查看本地迁移任务记录：

```bash
agentkit migrate . --framework dify list
```

## AgentKit 部署

迁移完成后进入输出目录，确认 `.agentkit/agentkit.yaml`，然后执行：

```bash
agentkit deploy
```


## 输出结果

迁移完成后，输出目录通常包含：

- 可直接执行 `agentkit deploy` 的 VeADK / AgentKit Runtime 工程。
- `.agentkit/agentkit.yaml` 部署配置。
- `convert_report.md` 迁移报告。
- `migration_plan.md` 迁移计划。
- `eval/` 评测用例。

如果源 Dify workflow 依赖未配置的知识库、Dify marketplace 插件或其他外部服务，迁移结果会保留工作流结构，并在报告中说明降级点。

## 示例输入

- Dify 是什么，能做什么？
- Dify 适合哪些使用场景？
- Dify 的定价与套餐方案是什么？
- 如何快速上手 Dify？

## 常见问题
- `node_config.yml` 必须提供吗？

  不是必须。它用于补充节点运行配置；没有该文件时，迁移会以 workflow 中已有配置为准。

- 外部依赖无法还原怎么办？

  迁移不会伪造外部调用成功。未配置的知识库、插件、HTTP 服务等会在迁移报告中说明，后续可以在输出工程中补齐配置。

## 代码许可

本工程遵循 Apache 2.0 License。
