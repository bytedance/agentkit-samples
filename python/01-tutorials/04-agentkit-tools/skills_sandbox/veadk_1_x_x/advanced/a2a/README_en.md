<!-- markdownlint-disable required-headers -->

# Invoke a Sandbox over A2A

`sandbox_a2a_invoke.py` creates or reuses an AgentKit Sandbox Session, sends a
message to the Session's `/a2a` endpoint, and polls the task until completion.

## Sandbox profiles

| Profile | Default | CreateSession environment variables |
| --- | --- | --- |
| `skill` | Yes | Omits `Envs`; model configuration is managed by the Skill Tool |
| `skill-env` | No | Injects `MODEL_AGENT_NAME`, `MODEL_AGENT_PROVIDER`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY` |

## Invoke a Skill Tool

Run this command from the `veadk_1_x_x` directory:

```bash
uv run --with agentkit-sdk-python==0.8.0 \
  python3 advanced/a2a/sandbox_a2a_invoke.py \
  --tool-id {{your_tool_id}} \
  --session-id skill-demo-1 \
  --prompt 'Hello'
```

`skill` is the default profile, so `--sandbox-profile` is not required. Do not
pass any `--model-*` arguments for this profile.

## Invoke a SkillEnv Tool

```bash
export MODEL_AGENT_API_KEY="{{your_model_api_key}}"

uv run --with agentkit-sdk-python==0.8.0 \
  python3 advanced/a2a/sandbox_a2a_invoke.py \
  --sandbox-profile skill-env \
  --tool-id {{your_tool_id}} \
  --session-id skill-env-demo-1 \
  --prompt 'Hello' \
  --model-provider openai \
  --model-name {{your_model_name}} \
  --model-base-url {{your_model_base_url}}
```

Model settings may also come from the AgentKit Sandbox configuration or the
corresponding `MODEL_AGENT_*` environment variables. For an OpenAI-compatible
Ark endpoint, use `openai` as the LiteLLM provider. Do not pass the AgentKit
`model_square` plan marker directly as a LiteLLM provider.

## Session reuse

Environment variables take effect only during CreateSession. When the script
finds an available Session with the same `--tool-id` and `--session-id`, it
reuses that Session. Use a new Session ID after changing the profile or model
configuration.

For example:

```bash
--session-id skill-demo-2
```

If an error still contains `model_square/<model-name>`, the script is usually
reusing a Session created with `MODEL_AGENT_PROVIDER=model_square`. Retry with
a new Session ID.
