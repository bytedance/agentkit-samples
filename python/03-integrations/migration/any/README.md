# Any 通用迁移 AgentKit Runtime 示例

## 概述

AgentKit Runtime 原生支持主流智能体框架，已兼容 LangChain、LangGraph、Strands、Google ADK，以及基于 Bedrock AgentCore Runtime 构建的项目。对于暂未显式适配、结构不固定的项目，可以使用 agentkit migration命令，结合codex sandbox的能力，发起通用迁移。

本目录展示 `--framework any` 的迁移链路：将已有 Python agent 项目提交给远端 Codex 沙箱分析，生成可在 AgentKit Runtime 上运行的 VeADK / AgentKit Runtime 工程。

本示例的源项目是一个 Strands 旅行规划 agent。这里使用 `--framework any`，目的是展示通用迁移能力如何自动理解项目结构，而不是要求用户手动声明具体框架。

## 原输入

输入目录是 `any_input/`，其中包含一个旅行规划 agent：

- 入口代码：`any_input/agent.py`
- 框架：Strands `Agent`
- 工具：城市资料检索、预算估算、交通建议
- 迁移目标：让 Codex 沙箱自动理解项目结构，并生成 VeADK / AgentKit Runtime 输出工程

## 安装依赖

在当前示例目录安装依赖：

```bash
pip install -r requirements.txt
```

也可以使用 `uv`：

```bash
uv pip install -r requirements.txt
```

## 环境变量

先准备 AgentKit 账号凭证和模型配置。

火山引擎国内版：

```bash
# AgentKit
export VOLCENGINE_ACCESS_KEY=""
export VOLCENGINE_SECRET_KEY=""

# 方舟模型
export MODEL_AGENT_NAME=""
export MODEL_AGENT_PROVIDER="openai"
export MODEL_AGENT_API_BASE="https://ark.cn-beijing.volces.com/api/v3/responses"
export MODEL_AGENT_API_KEY=""
```

BytePlus 海外版：

```bash
# BytePlus 模型
export MODEL_AGENT_NAME=""
export MODEL_AGENT_PROVIDER="openai"
export MODEL_AGENT_API_BASE="https://ark.ap-southeast.bytepluses.com/api/v3/"
export MODEL_AGENT_API_KEY=""

# BytePlus AgentKit
export BYTEPLUS_ACCESS_KEY=""
export BYTEPLUS_SECRET_KEY=""
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_REGION=ap-southeast-1
```



## 创建迁移任务

`create` 会真实发起远端迁移任务，建议确认环境变量和输入目录后再执行。执行前需要确保 `agentkit` CLI 命令已加载。

```bash
（激活uv）source .venv/bin/activate

# 如果已经有模型 key，可以映射给 migrate 远端 Codex 模型 key。
# 或者不设置这一行，在 create 命令后追加对应的 --codex-api-key-env 参数。
export AGENTKIT_MIGRATE_MODEL_API_KEY=""
cd <project_dir>/any/any_input

agentkit migrate . --framework any create --name any-test --output ../any_output \
    --codex-model <model_name> \
    --codex-api-key-env "" \
    --model-id <model_name> \
    --model-base-url https://ark.cn-beijing.volces.com/api/v3 \
    --model-api-key-env ""
```

该命令会把 `any_input/` 作为源项目提交给迁移任务，并将最终产物写入 `--output` 指定的目录。

## 查询和下载结果

查询任务状态并下载终态产物：

```bash
agentkit migrate . --framework any status --job-id <job_id>
```

或使用位置参数形式：

```bash
agentkit migrate . --framework any status <job_id>
```

查看本地迁移任务记录：

```bash
agentkit migrate . --framework any list
```

## 输出结果

迁移完成后，`--output` 指定目录会包含可直接执行 `agentkit deploy` 的 VeADK / AgentKit Runtime 工程，以及 `.agentkit/` 配置。具体文件以实际迁移产物为准。

## 部署

进入迁移输出目录，确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

部署环境中继续使用上面的 AgentKit 账号凭证和模型环境变量。

## 示例输入

- 我想带父母去北京玩 3 天，总预算 3000 元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
- 我想去西安玩 2 天，预算 1800 元，喜欢历史遗迹和当地小吃，请安排一个不太累的路线。

## 参数说明

- `--framework any`：使用通用 agentic migration。
- `create`：创建远端迁移任务。
- `status`：查询任务并下载结果。
- `list`：查看本地 `.agentkit/migrate/jobs` 记录。
- `--model-api-key-env` 不写时默认使用 `MODEL_AGENT_API_KEY`。

## License

Apache 2.0 License.
