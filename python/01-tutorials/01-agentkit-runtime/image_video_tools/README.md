# Image and Video Tools - 生图生视频工具

基于火山引擎 VeADK 和多媒体生成工具构建的创意内容生成示例，展示如何通过 Agent 生成图片和视频内容。

## 概述

本示例演示如何使用 VeADK 构建多智能体系统，根据文本描述生成图片或视频。

## 核心功能

- 单 Agent 架构：使用单一 Agent 协调所有工具
- 图像生成：将文字描述转换为图片
- 视频生成：基于图片或文字生成视频
- 内容搜索：使用 Web 搜索增强创作能力

## Agent 能力

```text
用户输入（文本描述）
    ↓
主 Agent (image_video_tools_agent)
    ├── web_search 工具（搜索背景信息）
    ├── image_generate 工具（生成图片）
    └── video_generate 工具（生成视频）
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **主 Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L38-L69) - image_video_tools_agent，负责理解用户意图并调用工具 |
| **内置工具** | `image_generate`, `video_generate`, `web_search` |
| **服务框架** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L81-L89) - AgentkitAgentServerApp，提供 HTTP 服务接口 |
| **客户端测试** | [client.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/client.py) - 测试客户端，用于调用部署的云端服务 |
| **项目配置** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/pyproject.toml) - 依赖管理 |

### 代码特点

**主 Agent 配置**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L38-L69)）：

```python
root_agent = Agent(
    name="image_video_tools_agent",
    description="调用 tools 生成图片或者视频",
    instruction="""
    你是一个生图生视频助手，具备图像生成和视频生成能力。有三个可用的工具：
    - web_search：用于搜索相关信息。
    - image_generate：用于生成图像。
    - video_generate：用于生成视频。

    ### 工作流程：

    1. 当用户提供输入时，根据用户输入，准备相关背景信息：
       - 若用户输入为故事或情节，直接调用 web_search 工具；
       - 若用户输入为其他类型（如问题、请求），则先调用 web_search 工具 (最多调用2次)，找到合适的信息。
    2. 根据准备好的背景信息，调用 image_generate 工具生成分镜图片。生成后，以 Markdown 图片列表形式返回，例如：
        ```
        ![分镜图片1](https://example.com/image1.png)
        ```
    3. 根据用户输入，判断是否需要调用 video_generate 工具生成视频。返回视频 URL 时，使用 Markdown 视频链接列表，例如：
        ```
        <video src="https://example.com/video1.mp4" width="640" controls>分镜视频1</video>
        ```
    
    ### 注意事项：
    - 输入输出中，任何涉及图片或视频的链接url，**绝对禁止任何形式的修改、截断、拼接或替换**，必须100%保持原始内容的完整性与准确性。        
    """,
    tools=[web_search, image_generate, video_generate],
)
```

**服务启动**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L81-L89)）：

```python
short_term_memory = ShortTermMemory(backend="local")

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
```

**使用示例**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L71-L79)）：


```python
async def main(prompts: list[str]):
    session_id = uuid.uuid4().hex
    for prompt in prompts:
        response = await runner.run(
            messages=prompt,
            session_id=session_id,
        )
        print(response)

# 示例提示词
asyncio.run(main([
    "请生成古文片段 落霞与孤鹜齐飞，秋水共长天一色 的首帧图片",
    "刚才的首帧图，生成视频。",
]))
```

## 目录结构说明

```bash
image_video_tools/
├── agent.py                    # Agent 应用入口
├── requirements.txt            # Python 依赖列表
├── pyproject.toml              # 项目配置（uv 依赖管理）
└── README.md                   # 项目说明文档
```

## 本地运行

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 开通多媒体生成服务：**

- 确保已开通图像生成和视频生成服务
- 参考 [视频生成文档](https://www.volcengine.com/docs/82379/1366799)

**3. 获取火山引擎访问凭证：**

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
cd 01-tutorials/01-agentkit-runtime/image_video_tools

# 使用 uv 安装依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 激活虚拟环境
source .venv/bin/activate
```

### 环境准备

```bash
# 火山方舟模型名称
export MODEL_AGENT_NAME=deepseek-v3-2-251201

# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### 启动服务

#### 方式一：直接运行服务（推荐）

```bash
# 启动 Agent 服务（默认端口 8000）
uv run agent.py

# 服务启动后，可通过以下方式测试：
# 1. 使用 client.py 测试
# 2. 使用 VeADK Web 调试界面
```

#### 方式二：使用 VeADK Web 调试界面

```bash
# 进入上级目录
cd python/01-tutorials/01-agentkit-runtime

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面提供图形化对话测试环境，支持实时查看生成的图片和视频。

## AgentKit 部署

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### AgentKit 云上部署

```bash
cd python/01-tutorials/01-agentkit-runtime/image_video_tools

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '请生成古文片段 落霞与孤鹜齐飞，秋水共长天一色 的首帧图片'
```

### 使用客户端测试

编辑 [client.py](client.py#L14-L16)，将 `base_url` 和 `api_key` 修改为 `agentkit.yaml` 中生成的 `runtime_endpoint` 和 `runtime_apikey` 字段：

```python
base_url = "http://<runtime_endpoint>"
api_key = "<runtime_apikey>"
```

运行客户端测试：

```bash
uv run client.py
```

## 示例提示词

### 图像生成

**基于文字描述生成图片**：

```text
用户：请生成古文片段 落霞与孤鹜齐飞，秋水共长天一色 的首帧图片
Agent：我来为您生成这个古文场景的图片...
      [调用 web_search 搜索背景信息]
      [调用 image_generate 生成图片]
      已生成图片，展现了落霞、孤鹜与秋水长天的意境。
      ![分镜图片1](https://example.com/image1.png)
```

### 视频生成

**基于文字描述生成视频**：

```text
用户：生成一段宇宙飞船在星际航行的视频
Agent：[调用 web_search 搜索相关背景]
      [调用 video_generate 生成视频]
      视频已生成，为您呈现宇宙飞船在星际航行的场景。
      <video src="https://example.com/video1.mp4" width="640" controls>宇宙飞船航行视频</video>
```

### 结合搜索增强

**基于搜索结果生成内容**：

```text
用户：搜索一下富士山的特点，然后生成一张富士山的图片
Agent：[调用 web_search 搜索富士山信息]
      [基于搜索结果，调用 image_generate 生成富士山图片]
      已为您生成富士山的图片，展现了雪山、樱花等特征。
```

## 效果展示

## 技术要点

### 单 Agent 架构

- **主 Agent**：负责理解用户意图，直接调用所有工具
- **工具集成**：所有工具（web_search, image_generate, video_generate）集成在主 Agent 中
- **工作流程**：搜索背景信息 → 生成图片 → 按需生成视频

### 内置工具

**图像生成工具**：

```python
from veadk.tools.builtin_tools.image_generate import image_generate
```

**视频生成工具**：

```python
from veadk.tools.builtin_tools.video_generate import video_generate
```

**Web 搜索工具**：

```python
from veadk.tools.builtin_tools.web_search import web_search
```

### 多轮对话上下文

- 使用 `session_id` 维护会话上下文
- 使用 `ShortTermMemory` 存储对话历史
- Agent 能理解上下文引用

### HTTP 服务接口

- 使用 `AgentkitAgentServerApp` 提供 HTTP 服务
- 默认端口 8000
- 支持 SSE 流式响应

### 工作流程

1. **用户输入**：提供文字描述
2. **Agent 理解**：分析用户意图，确定需要调用的工具
3. **背景搜索**（按需）：调用 web_search 搜索相关信息
4. **图片生成**：调用 image_generate 生成图片
5. **视频生成**（按需）：调用 video_generate 生成视频
6. **结果返回**：以 Markdown 格式返回图片/视频链接

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [视频生成工具文档](https://volcengine.github.io/veadk-python/tools/builtin/#video-generate)

## 代码许可

本工程遵循 Apache 2.0 License
