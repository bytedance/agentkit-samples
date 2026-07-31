# Strands Project Adaptation to AgentKit Runtime Sample

## Overview

This sample shows how to adapt an existing Strands project to AgentKit Runtime.

The sample project represents a user-owned Strands travel-planning agent. Its original business entry point is `agent.py:agent`, implemented as a zero-argument Strands `Agent` factory. The code registers a model, a system prompt, and simple local travel tools with Strands, then uses them to answer travel-planning questions with city notes, budget evaluation, and transportation suggestions.

You do not need to rewrite the original business logic during adaptation. `agentkit migrate` generates `agentkit_app.py` and `.agentkit/` configuration, and the generated Runtime app calls the original `agent.py:agent` through `StrandsAgentkitBridge`.

## Key Features

- Shows how a Strands `Agent` factory entry is called by AgentKit Runtime.
- Uses `@tool` to declare local travel-note search, budget estimation, and transportation recommendation tools.
- Uses Strands `OpenAIModel` for real model calls; the provider is determined by the `OpenAIModel` class, so `MODEL_AGENT_PROVIDER` is not required.
- Preserves the native Strands business code and adds the AgentKit Runtime adaptation through `agentkit migrate`.

## Agent Capabilities

This sample includes the following local tools:

- `search_travel_notes`: searches built-in city travel notes.
- `estimate_trip_budget`: estimates whether the budget is sufficient by city, days, and total budget.
- `recommend_transport`: recommends transportation by city and traveler type.

After adaptation, the call flow is:

```text
User question
    |
AgentKit Runtime
    |
agentkit_app.py
    |
StrandsAgentkitBridge
    |
agent.py:agent  # zero-argument factory that creates a Strands Agent
    |-- OpenAIModel / local demo model
    |-- search_travel_notes
    |-- estimate_trip_budget
    `-- recommend_transport
```

## Directory Layout

```bash
strands/
├── .env.example       # Model config variable names
├── README.md          # Chinese documentation
├── README_en.md       # English documentation
├── agent.py           # Native Strands Agent factory, tools, and model config
└── requirements.txt   # Dependencies split into native agent and AgentKit runtime sections
```

Running `agentkit migrate` in this directory generates `agentkit_app.py` and `.agentkit/`. Generated files do not need to be committed as part of the sample source.

## Local Run

### Install Dependencies

Use Python 3.10 or later. From this sample directory, run:

```bash
pip install -r requirements.txt
```

You can also use `uv`:

```bash
uv pip install -r requirements.txt
```

### Configure Environment

Copy `.env.example` to `.env` and keep the required model variable names in dotenv empty-value form:

```text
MODEL_AGENT_NAME=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=
```

Provide actual model values through shell environment variables:

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

When `MODEL_AGENT_NAME` and `MODEL_AGENT_API_KEY` are configured, the code creates a model with Strands `OpenAIModel`. The provider is determined by that class, so `MODEL_AGENT_PROVIDER` is not required. `MODEL_AGENT_API_BASE` may point to the Ark Responses endpoint; the sample normalizes it to the OpenAI-compatible API root `https://ark.cn-beijing.volces.com/api/v3` before passing it to `OpenAIModel`.

For Volcengine, export the account AK/SK credentials as environment variables:

```bash
export VOLCENGINE_ACCESS_KEY=
export VOLCENGINE_SECRET_KEY=
```

For BytePlus AgentKit, export these environment variables:

```bash
export BYTEPLUS_ACCESS_KEY=
export BYTEPLUS_SECRET_KEY=
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_REGION=ap-southeast-1
```

Account credentials are not written to `.env.example` or `.env`, and are not read by the native Strands agent business code.

If model env vars are not configured, the sample uses a local demo model so you can inspect the call flow before and after migration.

### Debug Locally

Run the native Strands Agent directly:

```bash
python agent.py
```

This command creates the Strands Agent returned by `agent.py:agent`, sends a fixed travel question to the agent, and prints a readable travel-planning result.

You can also debug the migrated Runtime app. First run:

```bash
agentkit migrate . \
  --framework strands \
  --entry agent.py:agent \
  --name migration-strands-travel \
  --verify \
  --force
```

Arguments:

- `--framework strands`: migrate as a Strands Agent.
- `--entry agent.py:agent`: specify the native zero-argument Strands Agent factory entry.
- `--verify`: run basic checks after generation.
- `--force`: overwrite old generated files if they already exist.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by the Strands Agent created from `agent.py:agent` and the original tools.

Deployment needs model env vars in the deployment environment. Export account credentials with the Volcengine or BytePlus block above:

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

## Example Prompts

- I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
- I want to visit Xi'an for 2 days with a budget of 1800 RMB. I like historical sites and local snacks. Please arrange a relaxed route.

## Expected Output

Running an example prompt makes the agent use local travel notes, budget, and transportation tools, then return a day-by-day itinerary with attractions, food, budget judgment, and transportation suggestions.

```text
北京3天旅行规划（示例模型输出）

第1天：故宫博物院，餐饮可安排北京烤鸭，节奏保持轻松。
第2天：天坛公园，餐饮可安排炸酱面，节奏保持轻松。
```

## FAQ

- What if model env vars are not configured?

  The sample uses a local demo model and returns readable output. After you configure `MODEL_AGENT_NAME`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY`, it switches to the real Strands `OpenAIModel`.

- Where should account credentials go?

  Do not write them to `.env.example` or `.env`. Before running `agentkit migrate` or `agentkit deploy`, export the matching Volcengine or BytePlus variables.

- Does the migration command rewrite `agent.py`?

  No. The migration command adds Runtime adaptation files, while the original Strands business entry remains unchanged.

## License

This project is licensed under the Apache 2.0 License.
