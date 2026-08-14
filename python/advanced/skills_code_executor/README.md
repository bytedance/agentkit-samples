# Skills Code Executor - 本地技能脚本执行示例

## 概述

本示例展示如何使用 Google ADK `SkillToolset` 加载本地 Skill，并通过
`UnsafeLocalCodeExecutor` 执行 Skill 自带的 Python 脚本。示例内置
`algorithmic-art` Skill，可根据标题、种子和调色板生成确定性的 SVG 图形。

> [!WARNING]
> `UnsafeLocalCodeExecutor` 会在 Agent 进程中执行代码，不提供沙箱隔离。仅加载并
> 执行经过审查的可信 Skill。不要用它执行用户提交的代码，也不要直接用于多租户
> 生产环境。

## 核心功能

- 使用 `load_skill_from_dir` 加载本地 `algorithmic-art` Skill
- 将 Skill 注册到 `SkillToolset`
- 为 `run_skill_script` 配置 `UnsafeLocalCodeExecutor`
- 通过 VeADK Agent 暴露 Skill 的发现、加载、资源读取和脚本执行能力
- 使用确定性 SVG 脚本演示参数传递和执行结果返回

## Agent 能力

本示例使用以下组件：

- 方舟大模型：`deepseek-v4-pro-260425`
- Google ADK Skills
- Google ADK `SkillToolset`
- Google ADK `UnsafeLocalCodeExecutor`
- VeADK Agent
- AgentKit Runtime

## 目录结构说明

```text
skills_code_executor/
├── README.md
├── __init__.py
├── agent.py
├── pyproject.toml
├── skills/
│   └── algorithmic-art/
│       ├── SKILL.md
│       └── scripts/
│           └── generate_svg.py
└── tests/
    └── test_agent.py
```

核心装配逻辑：

```python
from pathlib import Path as _Path

from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

skills_agent = SkillToolset(
    skills=[
        load_skill_from_dir(
            _Path(__file__).parent / "skills" / "algorithmic-art"
        ),
    ],
    code_executor=UnsafeLocalCodeExecutor(),
)
```

## 本地运行

### 前置准备

1. 安装 Python 3.12 或 3.13
2. 安装 [uv](https://docs.astral.sh/uv/)
3. 开通火山方舟模型服务并获取模型 API Key

### 依赖安装

```bash
cd python/advanced/skills_code_executor
uv sync
```

### 环境准备

```bash
export MODEL_AGENT_API_KEY={{your_model_api_key}}
export MODEL_AGENT_NAME=deepseek-v4-pro-260425
```

### 调试方法

```bash
uv run agent.py
```

服务默认监听 `0.0.0.0:8000`。也可以使用 VeADK Web 调试：

```bash
uv run veadk web
```

运行单元测试：

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -v
```

## AgentKit 部署

```bash
agentkit config
agentkit deploy
```

部署前请确认 `skills/algorithmic-art` 中只包含经过安全审查的代码。生产环境应优先
替换为具备进程、文件系统和网络隔离能力的 Code Executor。

## 示例提示词

```text
使用 algorithmic-art 技能生成一幅名为 Volcanic Rhythm 的几何 SVG。
种子使用 42，颜色使用 #0b132b、#5bc0be 和 #f4d35e，共生成 24 个图形。
```

## 效果展示

Agent 会先加载 `algorithmic-art` 的说明，再调用 `run_skill_script` 执行
`scripts/generate_svg.py`。脚本返回完整 SVG 文本；相同的种子、调色板和图形数量
会得到相同结果。

## 常见问题

### 为什么不应执行用户提供的代码

`UnsafeLocalCodeExecutor` 没有沙箱边界，执行代码拥有 Agent 进程的本地权限。本示例
只允许执行随可信 Skill 一起发布并经过代码审查的脚本。

### 为什么修改脚本后结果没有变化

确认当前服务加载的是修改后的 sample 目录，并重启 Agent 进程。Skill 资源在 Agent
启动时由 `load_skill_from_dir` 读取。

## 代码许可

本工程遵循 Apache 2.0 License。
