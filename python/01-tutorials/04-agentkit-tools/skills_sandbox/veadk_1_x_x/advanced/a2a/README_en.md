<!-- markdownlint-disable required-headers -->

# Invoke a Sandbox over A2A

`direct_sandbox_a2a_invoke.py` creates or reuses an AgentKit Sandbox Session,
sends a message to the Session's `/a2a` endpoint, and polls the task until
completion.

## Support Matrix

With `veadk-python==1.1.9`, these flows are supported:

| Scenario | Flow | Runtime Agent tools | Sample |
| --- | --- | --- | --- |
| Skills Sandbox synchronous delegation | `runtime Agent -> execute_skills -> Skills Sandbox` | `execute_skills`, without bash/code tools | `runtime_to_skills_sandbox_execute.py` |
| Skills Sandbox non-blocking tasks | `runtime Agent -> invoke_skill/poll_skill -> Skills Sandbox` | `SkillToolset`, `invoke_skill`, `poll_skill` | `runtime_to_skills_sandbox_invoke_poll.py` |
| AIO Sandbox code execution | `runtime Agent -> run_code -> AIO/script Sandbox` | `SkillToolset`, `run_code` | `runtime_to_aio_sandbox_run_code.py` |
| Direct Sandbox A2A invocation | `client script -> Sandbox /a2a` | No runtime Agent | `direct_sandbox_a2a_invoke.py` |

Notes:

- The first two Skills Sandbox flows both target the Skills Sandbox, where a
  sandbox-side VeADK Agent continues executing remote skills.
- The synchronous delegation flow uses `execute_skills`; one tool call waits for
  the final result.
- The non-blocking task flow uses `invoke_skill` / `poll_skill`, so the runtime
  Agent can explicitly observe A2A task states such as `submitted`, `working`,
  and `completed`.
- The AIO Sandbox code execution flow does not use `execute_skills`,
  `invoke_skill`, or `poll_skill`; it
  loads the remote registry in the runtime Agent and delegates code or shell
  execution to the AIO/script sandbox.
- In VeADK 1.1.9, the tool names are singular: `invoke_skill` and `poll_skill`,
  not `invoke_skills` or `poll_skills`.

## Sandbox profiles

| Profile | Default | CreateSession environment variables |
| --- | --- | --- |
| `skill` | Yes | Omits `Envs`; model configuration is managed by the Skill Tool |
| `skill-env` | No | Injects `MODEL_AGENT_NAME`, `MODEL_AGENT_PROVIDER`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY` |

## Invoke a Skill Tool

Run this command from the `veadk_1_x_x` directory:

```bash
uv run --with agentkit-sdk-python==0.8.0 \
  python3 advanced/a2a/direct_sandbox_a2a_invoke.py \
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
  python3 advanced/a2a/direct_sandbox_a2a_invoke.py \
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

## Skills Sandbox Synchronous Delegation

`runtime_to_skills_sandbox_execute.py` demonstrates the synchronous runtime
Agent flow:

```text
runtime Agent (skills=[ss-xxx], tools=[execute_skills])
  -> execute_skills
  -> Skills Sandbox A2A
  -> sandbox VeADK Agent executes remote skills
```

The runtime Agent exposes only `execute_skills`; it does not mount local
bash/code execution tools.

```bash
uv run python3 advanced/a2a/runtime_to_skills_sandbox_execute.py \
  --tool-id {{your_skills_sandbox_tool_id}} \
  --skill-space-id {{your_skill_space_id}} \
  --session-id remote-skills-demo-1 \
  --prompt 'What skills do you have?'
```

`--tool-id` is written to `AGENTKIT_TOOL_ID_SKILLS`, and `--skill-space-id`
is configured as `skills=[ss-xxx]` on the runtime Agent.

## Skills Sandbox Non-blocking Tasks

`runtime_to_skills_sandbox_invoke_poll.py` demonstrates the non-blocking Skills
Sandbox tool flow added in `veadk-python==1.1.9`:

```text
runtime Agent (SkillToolset remote registry + invoke_skill + poll_skill)
  -> invoke_skill
  -> Skills Sandbox A2A task
  -> poll_skill
  -> sandbox VeADK Agent executes remote skills
```

`invoke_skill` creates a non-blocking A2A task and returns a `task_id`.
`poll_skill` fetches task snapshots by `task_id`. The tool names are singular:
`invoke_skill` and `poll_skill`.

```python
from google.adk.tools.skill_toolset import SkillToolset
from veadk.skills import VeSkillRegistry
from veadk.tools.builtin_tools.invoke_skill import invoke_skill
from veadk.tools.builtin_tools.poll_skill import poll_skill

skill_toolset = SkillToolset(
    registry=VeSkillRegistry(skill_source_id=os.getenv("SKILL_SPACE_ID")),
)

agent = Agent(
    name="skill_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[skill_toolset, invoke_skill, poll_skill],
)
```

Run:

```bash
uv run python3 advanced/a2a/runtime_to_skills_sandbox_invoke_poll.py \
  --tool-id {{your_skills_sandbox_tool_id}} \
  --skill-space-id {{your_skill_space_id}} \
  --session-id remote-skills-poll-demo-1 \
  --prompt 'What skills do you have?'
```

Use this flow when the runtime Agent needs explicit control over the A2A task
lifecycle. If the runtime Agent only needs a single final result, prefer the
`execute_skills` sample.

## AIO Sandbox Code Execution

`runtime_to_aio_sandbox_run_code.py` loads remote-registry skills in the
runtime Agent and uses `run_code` to execute Python or shell commands in the
AIO/script sandbox:

```text
runtime Agent (SkillToolset remote registry + run_code)
  -> remote skills
  -> run_code
  -> AIO/script sandbox
```

This sample does not use `execute_skills`. It requires both a remote Skill
Space and an AIO/script Sandbox Tool ID. `SkillToolset` `run_skill_script`
calls are also backed by `run_code`, so skill scripts do not execute in the
runtime process.

```bash
uv run python3 advanced/a2a/runtime_to_aio_sandbox_run_code.py \
  --tool-id {{your_aio_or_script_sandbox_tool_id}} \
  --skill-space-id {{your_skill_space_id}} \
  --session-id aio-skills-demo-1 \
  --prompt 'Use Python to print Hello World and run it.'
```

`--tool-id` is written to `AGENTKIT_TOOL_ID_SCRIPT`, which is used by
`run_code` to create or reuse the code execution sandbox session.
