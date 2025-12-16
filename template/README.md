# AgentKit 样例模板

> 您向 `agentkit-samples` 项目提交的样例，需要符合以下目录结构，并保证内容完整：
>
> ```bash
> template
> ├── LICENSE               # 项目代码许可，默认为 Apache 2.0 协议
> ├── README.md             # 项目说明文档
> ├── agent.py              # 主程序文件，定义您的应用入口
> ├── assets                # 静态资源文件
> ├── config.yaml.example   # 配置文件示例，您可以根据需要修改
> ├── prompts               # 提示词文件目录
> ├── pyproject.toml        # 项目依赖管理文件
> ├── requirements.txt      # 项目依赖管理文件
> ├── sub_agents            # 子智能体目录
> ├── tools                 # 工具函数目录
> └── utils                 # 辅助函数目录
> ```
>
> 注意：
>
> - `config.yaml.example` 与 `.env.example` 文件可二选一
> - `pyproject.toml` 与 `requirements.txt` 文件可二选一
>
> ## README.md 规范
>
> 项目的 `README.md` 文件，需要与本文件内的各级标题保持一致。

## 概述

本项目为 Agentkit Sample 的模板工程，用来帮助您创建规范、标准的 Agent 样例，并能帮助用户快速部署到 AgentKit 平台。

## 核心功能

- 功能 1
- 功能 2

## Agent 能力

请根据您的 Agent 能力，在下方描述主要的火山引擎产品或 Agent 组件：

- 豆包大模型 / Seedance / Seedream
- 知识库
- 记忆库
- 内置工具
- 自定义工具
- Identity
- ...

## 目录结构说明

您应当在此详细说明每个目录的作用，以及其中包含的文件。

## 本地运行

### 前置准备

引导用户开通火山引擎相关服务、开通某模型权限等。如无需前置准备，同样需在此处标明。

### 依赖安装

您可以通过 `pip` 工具来安装本项目依赖：

```bash
pip install -r requirements.txt
```

或者使用 `uv` 工具来安装本项目依赖：

```bash
# 使用 `pyproject.toml` 管理依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 使用 `requirements.txt` 管理依赖
uv pip install -r requirements.txt
```

### 环境准备

说明您的环境配置文件中的具体内容。

### 调试方法

通常使用 `python` 来运行项目：

```bash
python ...
```

或者使用 `veadk web` 进行调试：

```bash
veadk web
```

## AgentKit 部署

您需要在此详细说明如何将本项目部署到 AgentKit 平台。

## 示例提示词

- 提示词 1
- 提示词 2
- ...

## 效果展示

您需要在此处展示项目的运行效果，例如截图、视频等。

您的截图、视频等素材资产应当放置于 `assets` 目录下。

## 常见问题

- 问题 1
- 问题 2

## 代码许可

本工程遵循 Apache 2.0 License
