# Dify 迁移 AgentKit Runtime 示例

## 概述

AgentKit Runtime 原生支持主流智能体框架，已兼容 LangChain、LangGraph、Strands、Google ADK，以及基于 Bedrock AgentCore Runtime 构建的项目。对于 Dify 导出的工作流，可以通过 `agentkit migrate` 将 workflow 输入交给远端 Codex Sandbox进行处理，并生成开箱即用，可部署到AgentKit Runtime的VeADK工程。

本Demo将展示 Dify advanced-chat 应用的迁移链路：从 Dify 导出的 workflow 出发，生成可直接执行 `agentkit deploy` 的 VeADK 项目。

## 原输入

输入是一个 Dify advanced-chat 应用，应用名称为「专属智能客服」。

源目录需要包含：

- `workflow.yml` 或 `workflow.yaml`：Dify 导出的 workflow。
- `node_config.yml`：可选，放在源目录内一起上传，用于定义 workflow 节点的运行配置。

## 环境变量

先准备 AgentKit 账号凭证和模型配置。

火山引擎：

```bash
# AgentKit
export VOLCENGINE_ACCESS_KEY=""
export VOLCENGINE_SECRET_KEY=""

# 方舟模型
export MODEL_AGENT_NAME=""
export MODEL_AGENT_PROVIDER="openai"
export MODEL_AGENT_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
export MODEL_AGENT_API_KEY=""

# `AGENTKIT_MIGRATE_MODEL_API_KEY` 是远端 Codex 沙箱使用的模型 key。
export AGENTKIT_MIGRATE_MODEL_API_KEY=""
```

BytePlus：

```bash
# BytePlus 模型
export MODEL_AGENT_NAME=""
export MODEL_AGENT_PROVIDER="openai"
export MODEL_AGENT_API_BASE="https://ark.ap-southeast.bytepluses.com/api/v3/"
export MODEL_AGENT_API_KEY=""
# `AGENTKIT_MIGRATE_MODEL_API_KEY` 是远端 Codex 沙箱使用的模型 key。
export AGENTKIT_MIGRATE_MODEL_API_KEY=""

# BytePlus AgentKit AKSK
export BYTEPLUS_ACCESS_KEY=""
export BYTEPLUS_SECRET_KEY=""
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_REGION=ap-southeast-1
```

## 创建迁移任务

`create` 会真实发起远端迁移任务，建议确认环境变量和输入目录后再执行。

```bash
cd <project_dir>
source .venv/bin/activate
command -v agentkit

cd dify/dify_input
# 使用当前目录作为工作目录
agentkit migrate . --framework dify create --name dify-migrate --output ../dify_output \
    --codex-model ep-xxx \
    --codex-api-key-env "" \
    --model-id <model_name> \
    --model-base-url https://ark.cn-beijing.volces.com/api/v3 \
    --model-api-key-env ""
```

该命令会把当前目录的 Dify workflow 作为源输入，并将最终产物写入 `--output` 指定的目录。

## 查询和下载结果

查询任务状态并下载终态产物：

```bash
agentkit migrate . --framework dify status --job-id <job_id>
```

或使用位置参数形式：

```bash
agentkit migrate . --framework dify status <job_id>
```

查看本地迁移任务记录：

```bash
agentkit migrate . --framework dify list
```

## 输出结果

迁移完成后，输出目录会包含：

- 可直接执行 `agentkit deploy` 的 VeADK / AgentKit Runtime 工程。
- `.agentkit/agentkit.yaml` 部署配置。
- `convert_report.md` 迁移报告。
- `migration_plan.md` 迁移计划。
- `eval/` 评测用例。

当前 Dify 输入里有一些外部依赖无法直接还原，例如未配置知识库、Dify marketplace 插件等。迁移结果会保留工作流结构，并在报告中明确说明这些降级点，不伪造外部调用成功。

## 部署

进入迁移输出目录，确认 `.agentkit/agentkit.yaml` 后即可执行 `agentkit deploy`。部署环境中继续使用上面的 AgentKit 账号凭证和模型环境变量。

## 参数说明

- `--framework dify`：按 Dify workflow 迁移。
- `create`：创建远端迁移任务。
- `status`：查询任务并下载结果。
- `list`：查看本地 `.agentkit/migrate/jobs` 记录。

## License

Apache 2.0 License.
