<!-- markdownlint-disable required-headers -->

# 通过 A2A 调用 Sandbox

`direct_sandbox_a2a_invoke.py` 会创建或复用 AgentKit Sandbox Session，然后通过
Session 的 `/a2a` 接口发送消息并轮询任务结果。

## 支持矩阵

当前 `veadk-python==1.1.9` 已支持以下链路：

| 场景 | 链路 | runtime Agent 工具 | 示例 |
| --- | --- | --- | --- |
| Skills Sandbox 同步委托 | `runtime Agent -> execute_skills -> Skills Sandbox` | `execute_skills`，不挂载 bash/code 工具 | `runtime_to_skills_sandbox_execute.py` |
| Skills Sandbox 非阻塞任务 | `runtime Agent -> invoke_skill/poll_skill -> Skills Sandbox` | `SkillToolset`、`invoke_skill`、`poll_skill` | `runtime_to_skills_sandbox_invoke_poll.py` |
| AIO Sandbox 代码执行 | `runtime Agent -> run_code -> AIO/script Sandbox` | `SkillToolset`、`run_code` | `runtime_to_aio_sandbox_run_code.py` |
| 直接调用 Sandbox A2A | `client script -> Sandbox /a2a` | 无 runtime Agent | `direct_sandbox_a2a_invoke.py` |

说明：

- 前两种 Skills Sandbox 链路的目标都是 Skills Sandbox，sandbox 内部由 VeADK Agent
  继续执行远程技能。
- 同步委托链路使用 `execute_skills`，一次工具调用等待最终结果。
- 非阻塞任务链路使用 `invoke_skill` / `poll_skill`，runtime Agent 可以显式感知
  A2A task 的 `submitted`、`working`、`completed` 等状态。
- AIO Sandbox 代码执行链路不使用 `execute_skills`、`invoke_skill` 或 `poll_skill`；它在 runtime
  Agent 中加载 remote registry，并把代码或 Shell 执行交给 AIO/script sandbox。
- VeADK 1.1.9 中工具名是单数：`invoke_skill`、`poll_skill`，不是
  `invoke_skills`、`poll_skills`。

## Sandbox profile

| Profile | 是否默认 | CreateSession 环境变量 |
| --- | --- | --- |
| `skill` | 是 | 不传递 `Envs`；模型配置由 Skill Tool 管理 |
| `skill-env` | 否 | 注入 `MODEL_AGENT_NAME`、`MODEL_AGENT_PROVIDER`、`MODEL_AGENT_API_BASE` 和 `MODEL_AGENT_API_KEY` |

## 调用 Skill Tool

在 `veadk_1_x_x` 目录中执行：

```bash
uv run --with agentkit-sdk-python==0.8.0 \
  python3 advanced/a2a/direct_sandbox_a2a_invoke.py \
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
  python3 advanced/a2a/direct_sandbox_a2a_invoke.py \
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

## Skills Sandbox 同步委托

`runtime_to_skills_sandbox_execute.py` 演示同步版 runtime Agent 链路：

```text
runtime Agent (skills=[ss-xxx], tools=[execute_skills])
  -> execute_skills
  -> Skills Sandbox A2A
  -> sandbox 内 VeADK Agent 执行远程技能
```

runtime Agent 只挂载 `execute_skills`，不会暴露本地 bash/code 执行工具。

```bash
uv run python3 advanced/a2a/runtime_to_skills_sandbox_execute.py \
  --tool-id {{your_skills_sandbox_tool_id}} \
  --skill-space-id {{your_skill_space_id}} \
  --session-id remote-skills-demo-1 \
  --prompt '你有哪些技能'
```

`--tool-id` 会写入 `AGENTKIT_TOOL_ID_SKILLS`，`--skill-space-id` 会作为
runtime Agent 的 `skills=[ss-xxx]` 配置。

## Skills Sandbox 非阻塞任务

`runtime_to_skills_sandbox_invoke_poll.py` 演示 `veadk-python==1.1.9` 新增的
非阻塞 Skills Sandbox 工具链路：

```text
runtime Agent (SkillToolset remote registry + invoke_skill + poll_skill)
  -> invoke_skill
  -> Skills Sandbox A2A task
  -> poll_skill
  -> sandbox 内 VeADK Agent 执行远程技能
```

`invoke_skill` 负责创建非阻塞 A2A task 并返回 `task_id`，`poll_skill`
负责按 `task_id` 获取任务快照。注意工具名是单数：`invoke_skill` 和
`poll_skill`。

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

运行示例：

```bash
uv run python3 advanced/a2a/runtime_to_skills_sandbox_invoke_poll.py \
  --tool-id {{your_skills_sandbox_tool_id}} \
  --skill-space-id {{your_skill_space_id}} \
  --session-id remote-skills-poll-demo-1 \
  --prompt '你有哪些技能'
```

这条链路适合需要由 runtime Agent 显式感知 A2A task 生命周期的场景；如果只需要
一次调用拿到最终结果，优先使用 `execute_skills` 示例。

## AIO Sandbox 代码执行

`runtime_to_aio_sandbox_run_code.py` 演示 remote registry 技能在 runtime Agent 中加载，
并通过 `run_code` 将代码或 Shell 命令放到 AIO/script sandbox 中执行：

```text
runtime Agent (SkillToolset remote registry + run_code)
  -> remote skills
  -> run_code
  -> AIO/script sandbox
```

这个样例不使用 `execute_skills`，需要配置远程 Skill Space 和 AIO/script
Sandbox Tool ID。`SkillToolset` 的 `run_skill_script` 也会通过 `run_code`
后端执行，避免技能脚本落到 runtime 本地执行。

```bash
uv run python3 advanced/a2a/runtime_to_aio_sandbox_run_code.py \
  --tool-id {{your_aio_or_script_sandbox_tool_id}} \
  --skill-space-id {{your_skill_space_id}} \
  --session-id aio-skills-demo-1 \
  --prompt '请用 Python 打印 Hello World 并执行'
```

`--tool-id` 会写入 `AGENTKIT_TOOL_ID_SCRIPT`，供 `run_code` 创建或复用代码执行
sandbox session。
