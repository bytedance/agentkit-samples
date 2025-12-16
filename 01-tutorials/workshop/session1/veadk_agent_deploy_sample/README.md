# Session 1 - VeADK Agent 的 AgentKit 化部署

## 概述

本示例展示如何将一个基于 VeADK (Volcano Engine Agent Development Kit) 构建的 Native Agent，通过 AgentKit CLI 工具链，快速适配并一键部署到火山引擎 AgentKit 平台上。

本示例中的 Agent (Neo) 是一位赛博朋克风格的咖啡师，拥有独特的个性设定。

## 核心功能

1. **Native Agent 开发**：使用 VeADK 框架构建具备完整 Persona 和流式交互能力的 Native Agent。
2. **CLI 自动化工具链**：使用 `agentkit init` 自动生成仅需的适配代码，零侵入式集成。
3. **标准化部署**：通过 `agentkit launch` 实现从本地代码到云端服务的无缝交付。

## Agent 能力

### Persona: Neo (Cyberpunk Barista)

- **身份**: Glitch Brew 的传奇调制师。
- **性格**: 颓废精英范，将服务视为对"有机生命"的观察。
- **语言风格**:
  - 使用"义体/链路/矩阵"等黑话隐喻。
  - 回答犀利、简洁，如同高纯度数据流。
  - 常用 Emoji: 💾, 💊, ⚡

## 目录结构说明

```bash
veadk_agent_deploy_sample/
├── veadk_agent.py          # 原始 VeADK Agent 实现 (核心逻辑)
├── agentkit-veadk_agent.py # AgentKit 适配后的入口文件 (由 init 命令自动生成)
├── agentkit.yaml           # 部署配置文件 (由 init 命令自动生成)
├── requirements.txt        # 依赖列表
└── README.md               # 说明文档
```

## 本地运行

### 1. 前置准备

首先确保安装项目依赖：

```bash
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
source .venv/bin/activate

# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### 2. 运行 VeADK Agent

直接运行原始的 `veadk_agent.py` 脚本，验证 Agent 的核心逻辑和 Persona 表现：

```bash
uv run veadk_agent.py
```

该脚本会模拟一次本地调用，终端将输出 Neo 对预设问题的回复（带有流式打字机效果）。

## AgentKit 部署

使用 AgentKit CLI，我们可以直接基于现有的 `veadk_agent.py` 完成从配置生成到云端部署的全过程。

### 1. 初始化配置 (Init)

使用 `init` 命令基于原始脚本生成适配 AgentKit 平台的入口文件和配置文件：

```bash
agentkit init -f veadk_agent.py
```

执行后，当前目录下会自动生成：

- `agentkit-veadk_agent.py`: 包含 AgentKitServer 适配代码的封装文件。
- `agentkit.yaml`: 包含服务定义、资源配置和镜像构建信息的部署描述文件。

### 2. 部署上线 (Launch)

确认配置无误后，通过 `launch` 命令将 Agent 部署到 AgentKit 平台：

```bash
agentkit launch
```

CLI 会自动完成代码打包、镜像构建、并将其推送至 AgentKit 云端运行时环境。部署成功后，会返回服务的访问 URL。

### 3. 在线测试 (Invoke)

部署完成后，使用 `invoke` 命令直接与云端实例进行交互，验证部署效果：

```bash
agentkit invoke 'Neo，你的机械义肢今天还稳定吗？给我来杯能让大脑过载的特调'
```

你将收到来自赛博朋克咖啡师 Neo 的云端实时回复。

## 示例提示词

- "Neo，你的机械义肢今天还稳定吗？给我来杯能让大脑过载的特调"
- "这里有什么推荐的饮品？"
- "你对现在的世界怎么看？"

## 效果展示

- **本地终端**：支持打字机效果的流式文本输出，模拟赛博朋克终端交互体验。
- **云端服务**：部署后提供标准的 SSE 流式 API，可被 Web 前端或其他客户端集成调用。

## 常见问题

- **Q: `agentkit init` 生成的文件可以修改吗？**
  - A: 可以。`agentkit-veadk_agent.py` 是为了适配平台入口标准而生成的，如果您的 Agent 逻辑有变动，通常只需修改原始的 `veadk_agent.py`，只有在需要自定义服务启动参数时才需修改生成文件。

- **Q: 部署失败如何排查？**
  - A: 检查 `agentkit.yaml` 中的配置是否正确，特别是 Python 版本和 `requirements.txt` 依赖是否完整。

## 代码许可

本工程遵循 Apache 2.0 License。
