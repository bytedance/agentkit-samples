# LangGraph Project Adaptation to AgentKit Runtime Sample

## Overview

This sample shows how to adapt an existing LangGraph project to AgentKit Runtime.

The sample represents a user-owned LangGraph travel-planning project. Its original entry point is `agent.py:agent`, implemented as a compiled `StateGraph`. A graph node uses LangChain `create_agent` to register the model, system prompt, and local LangChain tools. After receiving a travel question, the agent calls tools and generates attraction, food, budget, and transportation suggestions.

You do not need to rewrite the original business logic during migration. `agentkit migrate` generates `agentkit_app.py` and `.agentkit/` configuration, and the generated Runtime app calls the original `agent.py:agent` through `LangGraphAgentkitBridge(input_key="question")`.

## Key Features

- Shows how a LangGraph compiled graph entry point is called by AgentKit Runtime.
- Uses an outer LangGraph `StateGraph` to keep the `question` input entry.
- Uses LangChain `create_agent` inside a LangGraph node to orchestrate the model, prompt, and tools.
- Uses `@tool` to declare local travel-note search, budget estimation, and transportation recommendation tools.
- Uses `langchain_openai.ChatOpenAI` for real model calls; the provider is determined by the `ChatOpenAI` class, so `MODEL_AGENT_PROVIDER` is not required.
- Preserves the native LangGraph business code and adds the AgentKit Runtime adaptation through `agentkit migrate`.

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
LangGraphAgentkitBridge(input_key="question")
    |
agent.py:agent  # compiled StateGraph
    `-- call_react_agent
        `-- create_agent
            |-- ChatOpenAI / local demo model
            |-- search_travel_notes
            |-- estimate_trip_budget
            `-- recommend_transport
```

## Directory Layout

```bash
langgraph/
├── .env.example       # Model config variable names
├── README.md          # Chinese documentation
├── README_en.md       # English documentation
├── agent.py           # Native LangGraph graph, ReAct agent, tools, and LLM calls
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

Provide actual model values through shell environment variables. The model configuration is consistent with the other migration demos and uses an OpenAI-compatible Ark endpoint. This sample does not use separate Gemini configuration and does not require `GOOGLE_API_KEY`:

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

The code uses `langchain_openai.ChatOpenAI` to create an OpenAI-compatible model, so the provider is determined by that class and `MODEL_AGENT_PROVIDER` is not required. `MODEL_AGENT_API_BASE` uses the Ark Responses endpoint. The sample normalizes it to the OpenAI-compatible API root `https://ark.cn-beijing.volces.com/api/v3` before passing it to `ChatOpenAI`.

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

Account credentials are not written to `.env.example` or `.env`, and are not read by the native LangGraph agent business code.

If model env vars are not configured, the sample uses a local demo model so you can inspect the call flow before and after migration.

### Debug Locally

Run the native LangGraph Agent directly:

```bash
python agent.py
```

You can also debug the migrated Runtime app. First run:

```bash
agentkit migrate . \
  --framework langgraph \
  --entry agent.py:agent \
  --name migration-langgraph-travel \
  --input-key question \
  --verify \
  --force
```

Arguments:

- `--framework langgraph`: migrate as a LangGraph compiled graph.
- `--entry agent.py:agent`: specify the native Graph entry.
- `--input-key question`: write Runtime input into the `question` field.
- `--verify`: run basic checks after generation.
- `--force`: overwrite old generated files if they already exist.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by `agent.py:agent` and the original LangGraph nodes.

Deployment needs the same model env vars in the deployment environment. Export account credentials with the Volcengine or BytePlus block above:

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

## Example Prompts

- I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
- I want to visit Chengdu for 2 days with a budget of 2000 RMB. I like food and city neighborhoods. Please arrange a relaxed route.

## Expected Output

Running an example prompt makes the agent use local travel-note, budget, and transportation tools, then return a day-by-day itinerary with attractions, food, budget judgment, and transportation suggestions.

```text
北京3天旅行规划（示例模型输出）

第1天：故宫博物院 + 什刹海胡同
第2天：天坛公园 + 前门周边
```

## FAQ

- What if model env vars are not configured?

  The sample uses a local demo model and returns readable output. After you configure `MODEL_AGENT_NAME`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY`, it switches to a real OpenAI-compatible ChatModel.

- Where should account credentials go?

  Do not write them to `.env.example` or `.env`. Before running `agentkit migrate` or `agentkit deploy`, export the matching Volcengine or BytePlus variables.

- Does the migration command rewrite `agent.py`?

  No. The migration command adds Runtime adaptation files, while the original LangGraph business entry remains unchanged.

## License

This project is licensed under the Apache 2.0 License.
