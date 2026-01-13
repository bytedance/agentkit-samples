# Skills Sandbox - 使用 VeADK 和 AgentKit 构建具备 skills 能力的 Agent

基于火山引擎 VeADK 和 AgentKit 构建具备 skills 能力的 Agent。

## 概述

本示例是 AgentKit 的 "Skills Sandbox"，展示如何创建一个具备 skills 能力的 Agent。

## 核心功能

- 本地 Agent 运行，调用 aio (All in one) sandbox，运行 aio 中的 Agent，完成 skills 任务
- 支持从 tos 中加载自定义 skills
- 支持将 skills 任务结果上传到 tos
- 支持`单线程执行`(agent.py) 和`多线程并发` (parallel.py) 两种模式
- 支持本地调试和云端部署

## Agent 能力

```text
用户消息
    ↓
AgentKit 运行时
    ↓
Skills Sandbox
    ├── VeADK Agent (对话引擎)
    ├── ShortTermMemory (会话记忆)
    └── 火山方舟模型 (LLM)
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **Agent 服务** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/04-agentkit-tools/02_skills_sandbox/agent.py) - 主应用程序，定义 Agent 和记忆组件 |
| **测试客户端** | [client.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/04-agentkit-tools/02_skills_sandbox/client.py) - SSE 流式调用客户端 |
| **项目配置** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/04-agentkit-tools/02_skills_sandbox/pyproject.toml) - 依赖管理（uv 工具） |
| **AgentKit 配置** | agentkit.yaml - 云端部署配置文件 |
| **短期记忆** | 使用本地后端存储会话上下文 |

### 代码特点

**Agent 定义**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/04-agentkit-tools/02_skills_sandbox/agent.py#L11-L15)）：

```python
agent = Agent()
short_term_memory = ShortTermMemory(backend="local")

runner = Runner(
    agent=agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id
)
```

## 目录结构说明

```bash
02_skills_sandbox/
├── agent.py           # Agent 运行一个 skills 任务
├── parallel.py        # 并发进行多个 skills 任务
├── client.py          # 测试客户端（SSE 流式调用）
├── requirements.txt   # Python 依赖列表 （agentkit部署时需要指定依赖文件)
├── pyproject.toml     # 项目配置（uv 依赖管理）
├── agentkit.yaml      # AgentKit 部署配置（运行agentkit config之后会自动生成）
├── Dockerfile         # Docker 镜像构建文件（运行agentkit config之后会自动生成）
└── README.md          # 项目说明文档
```

## 本地运行

### 前置准备

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### 依赖安装

#### 1. 安装 uv 包管理器

```bash
# macOS / Linux（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 Homebrew（macOS）
brew install uv
```

#### 2. 初始化项目依赖

```bash
# 进入项目目录
cd python/01-tutorials/04-agentkit-tools/02_skills_sandbox
```

您可以通过 `pip` 工具来安装本项目依赖：

```bash
pip install -r requirements.txt
```

或者使用 `uv` 工具来安装本项目依赖：

```bash
# 如果没有 `uv` 虚拟环境，可以使用命令先创建一个虚拟环境
uv venv --python 3.12

# 使用 `pyproject.toml` 管理依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 使用 `requirements.txt` 管理依赖
uv pip install -r requirements.txt

# 激活虚拟环境
source .venv/bin/activate
```

### 环境准备

```bash
# 火山方舟模型名称
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

export AGENTKIT_TOOL_ID=<Your Tool ID>
```

### 调试方法

#### 单线程运行：使用 VeADK Web 调试界面，调试 agent.py

```bash
# 进入项目目录
cd python/01-tutorials/04-agentkit-tools/02_skills_sandbox

# 启动 VeADK Web 界面
veadk web --port 8080

# 在浏览器访问：http://127.0.0.1:8080
```

Web 界面提供图形化对话测试环境，支持实时查看消息流和调试信息。

此外，还可以使用命令行测试，调试 agent.py。

```bash
cd python/01-tutorials/04-agentkit-tools/02_skills_sandbox

# 启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000

# 新开终端，运行测试客户端
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 修改为 http://0.0.0.0:8000
uv run client.py
```

#### 多线程并发：使用命令行测试，调试 parallel.py

```bash
cd python/01-tutorials/04-agentkit-tools/02_skills_sandbox

# 运行多线程并发程序
uv run parallel.py
```

## AgentKit 部署

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

**3. 创建 AgentKit 工具：**

- 工具类型选择：预置工具 -> Skill Sandbox

![Skill Sandbox 创建](assets/images/skill-sandbox-iam-role.jpeg)

**4. 设置环境变量：**

```bash
# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### AgentKit 云上部署

```bash
cd python/01-tutorials/04-agentkit-tools/02_skills_sandbox

# 配置部署参数
# optional：如果 agentkit config 中不添加 --runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}}，可以在 AgentKit 控制台 智能体运行时 中，关键组件，选择 沙箱工具，并发布
agentkit config \
--agent_name agent_skills \
--entry_point 'agent.py' \
--runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} \
--launch_type cloud

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '使用 internal-comms skill 帮我写一个3p沟通材料，通知3p团队项目进度更新。关于产品团队，主要包括过去一周问题和未来一周计划，具体包括问题：写产品团队遇到的客户问题 (1. GPU+模型推理框架性能低于开源版本，比如时延高、吞吐低；2. GPU推理工具易用性差)，以及如何解决的；计划：明年如何规划GPU产品功能和性能优化 (1. 发力GPU基础设施对生图生视频模型的支持；2. GPU推理相关工具链路易用性提升)。其他内容，可以酌情组织。'

# 或使用 client.py 连接云端服务
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
uv run client.py
```

## 内置 skills 列表

- 记得修改一下 {YOUR_TOS_BUCKET_NAME}，这是 AgentKit 默认为用户创建的 tos 存储桶，格式为 `agentkit-platform-{your_account_id}`，`如果没有这个 tos 存储桶，需要自己创建`

| skills | 描述 | 示例提示词 |
| ------ | --- | --------- |
| tos-file-access | 将文件或目录上传至火山引擎TOS ，从URL下载文件。在以下情况使用此技能：（1）将智能体生成的文件或目录（如视频、图像、报告、输出文件夹）上传至TOS以便共享；（2）在智能体处理前从URL下载文件。 | 请运行以下工作流程：1. 使用 tos-file-access 从 `https://agentkit-skills.tos-cn-beijing.volces.com/upload/topk_benchmark.cpp` 下载一个 topk_benchmark.cpp 代码文件。2. 使用 code-optimization 完善这个代码，把my_topk_inplace函数写好，要求性能要非常好，要比代码里面的标准库还要好。3. 使用 tos-file-access 将最终输出目录（包括最终代码和报告）上传到存储桶 {YOUR_TOS_BUCKET_NAME}。 |
| code-optimization | 通过迭代改进（最多2轮）优化代码性能。对执行时间和内存使用情况进行基准测试，与基准实现进行比较，并生成详细的优化报告。支持C++、Python、Java、Rust等语言 | 参考上一行 tos-file-access 的提示词。 |
| veadk-python | 基于VeADK框架实现一个可运行Agent | 请运行以下工作流程：1. 使用 veadk-python skill ，写一个 VeADK Agent，能够通过提问 "hello" 来回复。2. 将写好的代码写入本地一个新的代码文件，然后使用 tos-file-access skill 把这个代码文件上传到存储桶 {YOUR_TOS_BUCKET_NAME}，最后把上传后的代码文件链接发给我。 |
| algorithmic-art | 详见 [algorithmic-art](https://github.com/anthropics/skills/tree/main/skills/algorithmic-art) | |
| brand-guidelines | 详见 [brand-guidelines](https://github.com/anthropics/skills/tree/main/skills/brand-guidelines) | |
| canvas-design | 详见 [canvas-design](https://github.com/anthropics/skills/tree/main/skills/canvas-design) | |
| doc-coauthoring | 详见 [doc-coauthoring](https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring) | |
| docx | 详见 [docx](https://github.com/anthropics/skills/tree/main/skills/docx) | |
| frontend-design | 详见 [frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | |
| internal-comms | 详见 [internal-comms](https://github.com/anthropics/skills/tree/main/skills/internal-comms) | |
| mcp-builder | 详见 [mcp-builder](https://github.com/anthropics/skills/tree/main/skills/mcp-builder) | |
| pdf | 详见 [pdf](https://github.com/anthropics/skills/tree/main/skills/pdf) | |
| pptx | 详见 [pptx](https://github.com/anthropics/skills/tree/main/skills/pptx) | |
| skill-creator | 详见 [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) | |
| slack-gif-creator | 详见 [slack-gif-creator](https://github.com/anthropics/skills/tree/main/skills/slack-gif-creator) | |
| theme-factory | 详见 [theme-factory](https://github.com/anthropics/skills/tree/main/skills/theme-factory) | |
| web-artifacts-builder | 详见 [web-artifacts-builder](https://github.com/anthropics/skills/tree/main/skills/web-artifacts-builder) | |
| webapp-testing | 详见 [webapp-testing](https://github.com/anthropics/skills/tree/main/skills/webapp-testing) | |
| xlsx | 详见 [xlsx](https://github.com/anthropics/skills/tree/main/skills/xlsx) | |

## 示例提示词

- 记得修改一下 {YOUR_TOS_BUCKET_NAME}，这是 AgentKit 默认为用户创建的 tos 存储桶，格式为 `agentkit-platform-{your_account_id}`，`如果没有这个 tos 存储桶，需要自己创建`
- 下载自己 tos 中的 skills 到 sandbox，需要在 `agentkit-platform-{your_account_id}` 这个 tos 存储桶中，`新建 skills 文件夹`，然后将需要的 skills 上传到这个文件夹
- 如果需要下载自己 tos 中的一些文件，提示词中举例的 tos url 不可用，需要替换为自己的 tos url

<style>
table th:first-of-type {
    width: 25%;
}
table th:nth-of-type(2) {
    width: 25%;
}
table th:nth-of-type(3) {
    width: 50%;
}
</style>

| 是否使用 skills sandbox 中内置 skills | 产物是否上传 tos | 示例提示词 |
| ----------------------------------- | -------------- | -------- |
| 使用内置 skills | 产物不上传 tos | 使用 internal-comms skill 帮我写一个3p沟通材料，通知3p团队项目进度更新。关于产品团队，主要包括过去一周问题和未来一周计划，具体包括问题：写产品团队遇到的客户问题 (1. GPU+模型推理框架性能低于开源版本，比如时延高、吞吐低；2. GPU推理工具易用性差)，以及如何解决的；计划：明年如何规划GPU产品功能和性能优化 (1. 发力GPU基础设施对生图生视频模型的支持；2. GPU推理相关工具链路易用性提升)。其他内容，可以酌情组织。 |
| 使用内置 skills | 产物上传 tos | 请运行以下工作流程：1. 使用 canvas-design skill 帮我创作一件基于几何图形的艺术绘图。2. 使用 tos-file-access skill 把产物上传到存储桶 {YOUR_TOS_BUCKET_NAME} 里。 |
| 下载自己 tos 中的 skills (注意，这里需要自己在 `agentkit-platform-{your_account_id}` bucket 中新建一个 skills 文件夹，并将需要的 skills，比如本例中的 `healthy-meal-planner` 上传到这个文件夹) | 产物不上传 tos | 我需要一个2人份的纯素高蛋白食谱，目标增肌。每周预算350元，喜欢30分钟内的快手菜。不喜欢蘑菇。使用 healthy-meal-planner skill 帮我制订一周的食谱。 |
| 下载自己 tos 中的 skills (注意，这里需要自己在 `agentkit-platform-{your_account_id}` bucket 中新建一个 skills 文件夹，并将需要的 skills，比如本例中的 `healthy-meal-planner` 上传到这个文件夹) | 产物上传 tos | 请运行以下工作流程：1. 我需要一个2人份的纯素高蛋白食谱，目标增肌。每周预算350元，喜欢30分钟内的快手菜。不喜欢蘑菇。使用 healthy-meal-planner skill 帮我制订一周的食谱。2. 将制订好的食谱写入文件 recipe.md，然后使用 tos-file-access skill 把这个文件上传到存储桶 {YOUR_TOS_BUCKET_NAME}，最后把上传后的文件链接发给我。 |
| 下载自己 tos 中一些文件 | 产物不上传 tos | 请运行以下工作流程：1. 使用 tos-file-access 从 `https://agentkit-skills.tos-cn-beijing.volces.com/upload/sample3_20251209_192229.xlsx` 下载一个 sample3_20251209_192229.xlsx 文件。2. 使用 xlsx 解析文件 sample3_20251209_192229.xlsx 的内容。3. 总结文件内容中的统计信息。 |
| 下载自己 tos 中一些文件 | 产物上传 tos | 请运行以下工作流程：1. 使用 tos-file-access 从 `https://agentkit-skills.tos-cn-beijing.volces.com/upload/topk_benchmark.cpp` 下载一个 topk_benchmark.cpp 代码文件。2. 使用 code-optimization 完善这个代码，把my_topk_inplace函数写好，要求性能要非常好，要比代码里面的标准库还要好。3. 使用 tos-file-access 将最终输出目录（包括最终代码和报告）上传到存储桶 {YOUR_TOS_BUCKET_NAME}。 |

## 效果展示

| 示例提示词 | 效果截图 |
| -------- | ------- |
| 请运行以下工作流程：1. 使用 veadk-python skill ，写一个 VeADK Agent，能够通过提问 'hello' 来回复。2. 执行一下代码确保没问题；3. 将验证好的代码发给我。 | ![veadk skill 效果截图](assets/images/veadk-skill.png) |
| 使用 internal-comms skill 帮我写一个3p沟通材料，通知3p团队项目进度更新。关于产品团队，主要包括过去一周问题和未来一周计划，具体包括问题：写产品团队遇到的客户问题 (1. GPU+模型推理框架性能低于开源版本，比如时延高、吞吐低；2. GPU推理工具易用性差)，以及如何解决的；计划：明年如何规划GPU产品功能和性能优化 (1. 发力GPU基础设施对生图生视频模型的支持；2. GPU推理相关工具链路易用性提升)。其他内容，可以酌情组织。 | ![internal-comms skill 效果截图](assets/images/internal-comms-skill.jpeg) |
| 请运行以下工作流程：1. 使用 canvas-design skill 帮我创作一件基于几何图形的艺术绘图。2. 使用 tos-file-access skill 把产物上传到存储桶 {YOUR_TOS_BUCKET_NAME} 里。 | ![canvas-design skill 效果截图](assets/images/cavas-design-skill.jpeg) |
| 我需要一个2人份的纯素高蛋白食谱，目标增肌。每周预算350元，喜欢30分钟内的快手菜。不喜欢蘑菇。使用 healthy-meal-planner skill 帮我制订一周的食谱。 | ![healthy-meal-planner skill 效果截图](assets/images/health-meal-planner-skill.jpeg) |
| 请运行以下工作流程：1. 我需要一个2人份的纯素高蛋白食谱，目标增肌。每周预算350元，喜欢30分钟内的快手菜。不喜欢蘑菇。使用 healthy-meal-planner skill 帮我制订一周的食谱。2. 将制订好的食谱写入文件 recipe.md，然后使用 tos-file-access skill 把这个文件上传到存储桶 {YOUR_TOS_BUCKET_NAME}，最后把上传后的文件链接发给我。 | ![healthy-meal-planner skill 上传结果到 TOS 效果截图](assets/images/health-meal-planner-skill-tos.png) |

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## 代码许可

本工程遵循 Apache 2.0 License
