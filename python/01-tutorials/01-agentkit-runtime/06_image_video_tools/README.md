# Image and Video Tools - 生图生视频工具

基于火山引擎 VeADK 和多媒体生成工具构建的创意内容生成示例，展示如何通过多智能体协作生成图片和视频内容。

## 概述

本示例演示如何使用 VeADK 构建多智能体系统，根据文本描述生成图片或视频。

## 核心功能

- 多智能体架构：主 Agent 协调多个子 Agent
- 图像生成：将文字描述转换为图片
- 视频生成：基于图片或文字生成视频
- 内容搜索：使用 Web 搜索增强创作能力

## Agent 能力

```text
用户输入（文本描述）
    ↓
主 Agent (eposide_generator)
    ├── Image Generator (图像生成子 Agent)
    │   └── image_generate 工具
    │
    ├── Video Generator (视频生成子 Agent)
    │   └── video_generate 工具
    │
    └── Web Search (内容搜索)
        └── web_search 工具
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **主 Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L37-L43) - eposide_generator，协调子 Agent |
| **图像生成 Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L30-L35) - image_generator，生成图片 |
| **视频生成 Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L23-L28) - video_generator，生成视频 |
| **内置工具** | `image_generate`, `video_generate`, `web_search` |
| **项目配置** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/pyproject.toml) - 依赖管理（uv 工具） |

### 代码特点

**子 Agent 定义**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L23-L35)）：

```python
video_generator = Agent(
    name="video_generator",
    description="视频生成 Agent",
    instruction="你是一个原子化的 Agent，具备视频生成能力，每次执行完毕后，考虑回到主 Agent。",
    tools=[video_generate],
)

image_generator = Agent(
    name="image_generator",
    description="图像生成 Agent",
    instruction="你是一个原子化的 Agent，具备图像生成能力，每次执行完毕后，考虑回到主 Agent。",
    tools=[image_generate],
)
```

**主 Agent 配置**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L37-L43)）：

```python
root_agent = Agent(
    name="eposide_generator",
    description="调用子Agents生成图片或者视频",
    instruction="""你可以根据用户输入的一段小文字来生成视频或者生成图片""",
    sub_agents=[image_generator, video_generator],
    tools=[web_search],
)
```

**使用示例**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L47-L67)）：

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
06_image_video_tools/
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
- 参考 [视频生成文档](https://www.volcengine.com/docs/6791/1106485)

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
cd 01-tutorials/01-agentkit-runtime/06_image_video_tools
```

使用 `uv` 工具来安装本项目依赖：

```bash
# 如果没有 `uv` 虚拟环境，可以使用命令先创建一个虚拟环境
uv venv --python 3.12

# 使用 `pyproject.toml` 管理依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

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
```

### 调试方法

#### 方式一：使用 VeADK Web 调试界面

```bash
# 进入上级目录
cd python/01-tutorials/01-agentkit-runtime

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面提供图形化对话测试环境，支持实时查看生成的图片和视频。

#### 方式二：命令行测试（推荐学习）

```bash
# 运行示例脚本
uv run agent.py

# 脚本会依次执行两个任务：
# 1. 生成古文片段的图片
# 2. 基于图片生成视频
```

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
cd python/01-tutorials/01-agentkit-runtime/06_image_video_tools

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '请生成古文片段 落霞与孤鹜齐飞，秋水共长天一色 的首帧图片'

# 或使用 client.py 连接云端服务
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
# 按需修改 client.py，第 56 行，请求的内容
uv run client.py
```

## 示例提示词

### 图像生成

**基于文字描述生成图片**：

```text
用户：请生成古文片段 落霞与孤鹜齐飞，秋水共长天一色 的首帧图片
Agent：我来为您生成这个古文场景的图片...
      [调用 image_generator → image_generate 工具]
      已生成图片，展现了落霞、孤鹜与秋水长天的意境。
```

### 视频生成

**基于图片生成视频**：

```text
用户：刚才的首帧图，生成视频。
Agent：我来基于刚才的图片生成视频...
      [调用 video_generator → video_generate 工具]
      视频已生成，为您呈现动态的古文意境。
```

### 创意场景

**宇宙科幻场景**：

```text
用户：生成一个宇宙飞船在星际航行的场景图片
Agent：[生成科幻风格的宇宙飞船图片]

用户：把这张图片做成视频
Agent：[生成宇宙飞船航行的动态视频]
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

### 多智能体架构

- **主 Agent**：负责理解用户意图，协调子 Agent
- **子 Agent**：专注于单一功能（图像或视频生成）
- **原子化设计**：每个子 Agent 完成任务后返回主 Agent
- **工具隔离**：每个子 Agent 只拥有特定工具

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
- 支持连续生成（先图片，后视频）
- Agent 能理解"刚才的图片"等上下文引用

### 工作流程

1. **用户输入**：提供文字描述
2. **主 Agent 理解**：分析是图片还是视频需求
3. **委托子 Agent**：调用对应的子 Agent
4. **工具执行**：子 Agent 调用生成工具
5. **结果返回**：生成的图片/视频返回给用户

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [视频生成工具文档](https://volcengine.github.io/veadk-python/tools/builtin/#video-generate)

## 代码许可

本工程遵循 Apache 2.0 License
