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

This sample includes:

- A Strands `Agent` factory application entry.
- Strands tools.
- An OpenAI-compatible model node, with a local demo model fallback when model env vars are absent.
- Local business tools for travel notes, budget estimation, and transportation suggestions.

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
├── .env.example       # Example model config and AgentKit command credentials
├── README.md          # Chinese documentation
├── README_en.md       # English documentation
├── agent.py           # Native Strands Agent factory, tools, and model config
├── project.yaml       # Project metadata
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

Copy `.env.example` to `.env`, then fill in model config and the Volcengine AK/SK needed by AgentKit commands:

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

When `MODEL_AGENT_NAME` and `MODEL_AGENT_API_KEY` are configured, the code creates a model with Strands `OpenAIModel`. The provider is determined by that class, so `MODEL_AGENT_PROVIDER` is not required. `MODEL_AGENT_API_BASE` may point to the Ark Responses endpoint; the sample normalizes it to the OpenAI-compatible API root `https://ark.cn-beijing.volces.com/api/v3` before passing it to `OpenAIModel`.

`VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` are not read by the native Strands agent business code. They are kept because `agentkit migrate` and `agentkit deploy` need them.

If model env vars are not configured, the sample uses a local demo model so you can inspect the call flow before and after migration.

### Debug Locally

Run the native Strands Agent directly:

```bash
python agent.py
```

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

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by the Strands Agent created from `agent.py:agent` and the original tools.

Deployment needs model env vars and the Volcengine AK/SK required by AgentKit:

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
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

- Why keep `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY`?

  They are not read by the native Strands agent business code, but `agentkit migrate` and `agentkit deploy` need them.

- Does the migration command rewrite `agent.py`?

  No. The migration command adds Runtime adaptation files, while the original Strands business entry remains unchanged.
