# LangChain Project Adaptation to AgentKit Runtime Sample

## Overview

This sample shows how to adapt an existing LangChain project to AgentKit Runtime.

The sample represents a user-owned LangChain travel-planning project. Its original entry point is `agent.py:agent`, created directly with LangChain `create_agent`. It registers a model, system prompt, and local travel tools, accepts OpenAI messages format input, then lets the LangChain agent call tools and generate attraction, food, budget, and transportation suggestions.

You do not need to rewrite the original business logic during migration. `agentkit migrate` generates `agentkit_app.py` and `.agentkit/` configuration, and the generated Runtime app calls the original `agent.py:agent` through `LangChainAgentkitBridge`.

## Key Features

- Shows how a LangChain agent entry point is called by AgentKit Runtime.
- Uses LangChain `create_agent` to organize the model, prompt, and tools.
- Uses `@tool` to declare local travel-note search, budget estimation, and transportation recommendation tools.
- Preserves the native LangChain business code and adds the AgentKit Runtime adaptation through `agentkit migrate`.

## Agent Capabilities

This sample includes the following local tools:

- `search_travel_notes`: searches built-in city travel notes.
- `estimate_trip_budget`: estimates whether the budget is sufficient by city, days, and total budget.
- `recommend_transport`: recommends transportation by city and traveler type.

After migration, the call flow is:

```text
User question
    |
AgentKit Runtime
    |
agentkit_app.py
    |
LangChainAgentkitBridge
    |
agent.py:agent
    |-- create_agent
    |-- search_travel_notes
    |-- estimate_trip_budget
    |-- recommend_transport
    `-- ChatOpenAI
```

## Directory Layout

```bash
langchain/
├── .env.example       # Model config variable names
├── README.md          # Chinese documentation
├── README_en.md       # English documentation
├── agent.py           # Native LangChain agent and tools
└── requirements.txt   # Python dependencies
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

The code uses `langchain_openai.ChatOpenAI`, so the provider is determined by that class and `MODEL_AGENT_PROVIDER` is not required. `MODEL_AGENT_API_BASE` may point to the Ark Responses endpoint. The sample normalizes it to the OpenAI-compatible API root `https://ark.cn-beijing.volces.com/api/v3` before passing it to `ChatOpenAI`.

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

Account credentials are not written to `.env.example` or `.env`, and are not read by the native LangChain agent.

Set `MODEL_AGENT_NAME` and `MODEL_AGENT_API_KEY` before running the native LangChain agent.

### Debug Locally

Run the native LangChain Agent directly:

```bash
python agent.py
```

This command calls `agent.py:agent`, sends a fixed travel question to the agent, and uses the configured OpenAI-compatible model for one real conversation.

You can also debug the migrated Runtime app. First run:

```bash
agentkit migrate . \
  --framework langchain \
  --entry agent.py:agent \
  --name migration-langchain-travel \
  --input-key messages \
  --compat langserve \
  --verify
```

Arguments:

- `--framework langchain`: migrate as a LangChain Runnable.
- `--entry agent.py:agent`: specify the native Agent entry.
- `--input-key messages`: write Runtime input into the `messages` field.
- `--compat langserve`: generate LangServe-compatible routes.
- `--verify`: run basic checks after generation.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by `agent.py:agent` and the original LangChain tools.

Deployment needs model env vars in the deployment environment. Export account credentials with the Volcengine or BytePlus block above:

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

## Example Prompts

- I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
- I want to visit Chengdu for 2 days with a budget of 2000 RMB. I like food and city neighborhoods. Please arrange a relaxed route.

## Expected Output

Running an example prompt makes the agent use the LangChain local travel-note, budget, and transportation tools, then return a day-by-day itinerary with attractions, food, budget judgment, and transportation suggestions.

```text
北京3天旅行规划（预算3000元，带父母/长辈）

需求摘要：偏好历史文化, 胡同街区, 当地美食, 轻松慢游。
预算建议：北京3天总预算3000元，人均每日约1000元，预算判断：比较宽松。
```

## FAQ

- What if model env vars are not configured?

  Configure `MODEL_AGENT_NAME` and `MODEL_AGENT_API_KEY` first. `MODEL_AGENT_API_BASE` is optional; when it is set to the Ark Responses endpoint, the sample normalizes it to the OpenAI-compatible API root.

- Where should account credentials go?

  Do not write them to `.env.example` or `.env`. Before running `agentkit migrate` or `agentkit deploy`, export the matching Volcengine or BytePlus variables.

- Does the migration command rewrite `agent.py`?

  No. The migration command adds Runtime adaptation files, while the original LangChain business entry remains unchanged.

## License

This project is licensed under the Apache 2.0 License.
