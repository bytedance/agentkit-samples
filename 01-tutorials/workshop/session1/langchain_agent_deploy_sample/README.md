# Session 1 - 标准 LangChain Agent 的 AgentKit 化改造

## 概述

本 Workshop 旨在演示如何将一个基于 LangChain 构建的标准 Agent，通过 AgentKit SDK Python 进行轻量级改造，使其能够一键部署到火山引擎 AgentKit 平台上。

### Agent 改造指南

我们将对比 `langchain_agent.py` (原生实现) 和 `agent.py` (AgentKit 适配版)，改造过程仅需以下 **3 点** 极小改动：

1. **引入 SDK 并初始化应用**

    ```python
    # 引入 AgentKit SDK
    from agentkit.apps import AgentkitSimpleApp
    
    # 初始化应用实例
    app = AgentkitSimpleApp()
    ```

2. **标记入口函数**
    使用 `@app.entrypoint` 装饰器标记您的主逻辑函数。

    ```python
    @app.entrypoint
    async def run(payload: dict, headers: dict):
        # 您的业务逻辑...
    ```

3. **按照标准协议返回**
    将原本直接打印到控制台的输出，改为 `yield` 返回标准 JSON 格式的 Event 数据。

    ```python
    # 原生 LangChain: print(chunk)
    # AgentKit 适配:
    yield json.dumps(event_data)
    ```

这些改动是非侵入式的，您原有的 Chain 定义、Tool 定义和 Prompt 逻辑完全不需要修改。

## 核心功能

1. **构建 LangChain Agent**：使用 LangChain 1.0 标准范式构建具备工具调用能力的 ReAct Agent。
2. **AgentKit 快速适配**：通过 SDK 将本地 Agent 转换为生产级微服务，无需修改核心 Chain 逻辑。
3. **云端一键部署**：利用 AgentKit CLI 实现代码打包、镜像构建及环境变量的自动同步。

## Agent 能力

本 Agent 具备以下基础能力：

- **自动化推理**：基于 ReAct 范式，自动分析用户问题并规划工具调用顺序。
- **工具调用**：
  - `get_word_length`: 计算单词长度。
  - `add_numbers`: 执行数值加法运算。
- **流式响应**：支持 SSE 标准协议，实时输出思考过程和最终结果。

## 目录结构说明

```bash
session1/
├── agent.py               # 适配后的 AgentKit 应用 (核心文件)
├── langchain_agent.py     # 适配前的原生 LangChain 脚本 (对比参考)
├── local_client.py        # 本地流式调用测试客户端
├── agentkit.yaml          # 部署配置文件
├── .env                   # 环境变量配置文件 (部署时自动同步)
└── README.md              # 说明文档
```

## 本地运行

### 前置准备

1. **依赖安装**

   ```bash
   uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
   source .venv/bin/activate
   ```

2. **配置环境变量**

   ```bash
   cp .env.sample .env
   # 编辑 .env 文件，填入 OPENAI_API_KEY 等必填项

   # 火山引擎访问凭证（必需）
   export VOLCENGINE_ACCESS_KEY=<Your Access Key>
   export VOLCENGINE_SECRET_KEY=<Your Secret Key>
   ```

### 调试方法

**方式一：运行原生脚本** (验证 Agent 逻辑)

```bash
uv run langchain_agent.py
```

**方式二：运行 AgentKit 服务** (模拟生产环境)

```bash
# 启动服务 (监听 8000 端口)
uv run agent.py

# 在新终端运行客户端测试
uv run client.py
```

## AgentKit 部署

部署过程完全自动化，支持 `.env` 环境变量自动同步。

### 1. 初始化配置

```bash
agentkit config
```

此命令会引导您选择项目空间和镜像仓库等信息，生成 `agentkit.yaml`。

### 2. 部署上线

```bash
agentkit launch
```

> **重要**：`agentkit launch` 命令会自动读取您本地项目根目录下的 `.env` 文件，并将其中的所有环境变量自动注入到云端 Runtime 环境中。这意味着您**无需**在控制台手动配置 `OPENAI_API_KEY` 或 `MODEL_NAME` 等敏感信息，CLI 帮您完成了一切环境同步工作，确保云端运行环境与本地完全一致。

### 3. 在线测试

部署完成后，您可以使用 CLI 直接调用云端 Agent：

```bash
# <URL> 是 launch 命令输出的服务访问地址
agentkit invoke 'Hello, can you calculate 10 + 20 and tell me the length of the word "AgentKit"?'
```

## 示例提示词

- "What is the length of the word 'Volcengine'?"
- "Calculate 123 + 456."
- "Hello, can you calculate 10 + 20 and tell me the length of the word 'AgentKit'?"
- "Tell me a fun fact about Python." (此Agent不具备通用知识，会尝试使用工具或拒绝回答)

## 效果展示

- **本地脚本**：终端直接输出 ReAct 思考链，展示 Agent 的推理过程和最终结果。
- **HTTP 服务**：客户端接收 SSE 流式事件，包含详细的 `on_llm_chunk` (LLM思考过程)、`on_tool_start` (工具调用开始)、`on_tool_end` (工具调用结束) 等状态信息，提供丰富的交互体验。

## 常见问题

- **Q: 为什么提示 API Key 无效？**
  - A: 请确保 `.env` 文件中的 `OPENAI_API_KEY` 或其他模型服务商的 API Key 配置正确，且 `OPENAI_API_BASE` 与您使用的服务商（如火山方舟、OpenAI）匹配。

- **Q: 部署时环境变量未生效？**
  - A: 请确认 `.env` 文件位于运行 `agentkit launch` 命令的当前项目根目录下。CLI 会自动查找并同步该文件。

- **Q: Agent 无法回答通用知识问题？**
  - A: 本示例 Agent 主要演示工具调用能力，未集成通用知识库。如需回答通用知识，请扩展 Agent 的工具集或连接到知识库。

## 代码许可

本工程遵循 Apache 2.0 License。
