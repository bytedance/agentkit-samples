<!-- markdownlint-disable required-headers -->

# 通过 A2A 调用 Sandbox

`sandbox_a2a_invoke.py` 会创建或复用 AgentKit Sandbox Session，然后通过
Session 的 `/a2a` 接口发送消息并轮询任务结果。

## Sandbox profile

| Profile | 是否默认 | CreateSession 环境变量 |
| --- | --- | --- |
| `skill` | 是 | 不传递 `Envs`；模型配置由 Skill Tool 管理 |
| `skill-env` | 否 | 注入 `MODEL_AGENT_NAME`、`MODEL_AGENT_PROVIDER`、`MODEL_AGENT_API_BASE` 和 `MODEL_AGENT_API_KEY` |

## 调用 Skill Tool

在 `veadk_1_x_x` 目录中执行：

```bash
uv run --with agentkit-sdk-python==0.8.0 \
  python3 advanced/a2a/sandbox_a2a_invoke.py \
  --tool-id {{your_tool_id}} \
  --session-id skill-demo-1 \
  --prompt '你好'
```

`skill` 是默认 profile，因此无需传 `--sandbox-profile`，也不要传任何
`--model-*` 参数。

## 调用 SkillEnv Tool

```bash
export MODEL_AGENT_API_KEY="{{your_model_api_key}}"

uv run --with agentkit-sdk-python==0.8.0 \
  python3 advanced/a2a/sandbox_a2a_invoke.py \
  --sandbox-profile skill-env \
  --tool-id {{your_tool_id}} \
  --session-id skill-env-demo-1 \
  --prompt '你好' \
  --model-provider openai \
  --model-name {{your_model_name}} \
  --model-base-url {{your_model_base_url}}
```

模型参数也可以来自 AgentKit Sandbox 配置或对应的 `MODEL_AGENT_*` 环境变量。
对于 OpenAI-compatible 的 Ark 地址，LiteLLM provider 应使用 `openai`，不要将
AgentKit 的 `model_square` 套餐标识直接作为 LiteLLM provider。

## Session 复用

环境变量只在 CreateSession 时生效。脚本发现相同 `--tool-id` 和
`--session-id` 的可用 Session 后会直接复用，因此修改 profile 或模型配置后，
需要使用新的 Session ID 才能创建带有新配置的 Session。

例如：

```bash
--session-id skill-demo-2
```

如果错误中仍出现 `model_square/<model-name>`，通常表示复用了之前注入
`MODEL_AGENT_PROVIDER=model_square` 的 Session。请使用新的 Session ID 重试。
