# A2A Skill Sandbox 调用示例

## 概述

本示例演示如何创建或复用 AgentKit Skills Sandbox Session，并通过沙箱暴露的
`/a2a` 端点发起 Agent-to-Agent 调用。它是一个独立的高级示例，不修改
`python/01-tutorials/04-agentkit-tools/skills_sandbox` 下的存量教程逻辑。

## 目录结构

```text
a2a_skill_sandbox/
├── README.md
├── __init__.py
├── pyproject.toml
├── sandbox_a2a_client.py
└── tests/
    └── test_sandbox_a2a_client.py
```

## Sandbox profile

| Profile | 是否默认 | CreateSession 环境变量 |
| --- | --- | --- |
| `skill` | 是 | 不传 `Envs`；模型配置由 Skill Tool / 沙箱镜像自身管理 |
| `skill-env` | 否 | 注入 `MODEL_AGENT_NAME`、`MODEL_AGENT_PROVIDER`、`MODEL_AGENT_API_BASE` 和 `MODEL_AGENT_API_KEY` |

## 调用 Skill Tool

在本目录执行：

```bash
uv run python sandbox_a2a_client.py \
  --tool-id {{your_tool_id}} \
  --session-id skill-demo-1 \
  --prompt '你有哪些技能'
```

`skill` 是默认 profile。使用这个 profile 时不要传 `--model-*` 参数，因为
CreateSession 不会注入模型环境变量。

## 调用 SkillEnv Tool

```bash
uv run python sandbox_a2a_client.py \
  --sandbox-profile skill-env \
  --tool-id {{your_tool_id}} \
  --session-id skill-env-demo-1 \
  --prompt '你好' \
  --model-provider openai \
  --model-name {{your_model_name}} \
  --model-base-url {{your_model_base_url}} \
  --model-api-key {{your_model_api_key}}
```

模型参数也可以来自 AgentKit Sandbox CLI 配置。对于 OpenAI-compatible 的 Ark
地址，LiteLLM provider 应使用 `openai`。

## Session 复用

环境变量只在 CreateSession 时生效。相同 `--tool-id` 和 `--session-id` 的可用
Session 会被复用；修改 profile 或模型配置后，请换一个新的 `--session-id`。

## 单测

单测使用 mock AgentKit CLI 模块验证调用契约，不需要真实 Tool ID：

```bash
UV_CACHE_DIR=/private/tmp/uv-cache-agentkit-samples \
  uv run --no-sync python -m unittest discover \
  -s tests -p 'test_*.py'
```

## 代码许可

本工程遵循 Apache 2.0 License。
