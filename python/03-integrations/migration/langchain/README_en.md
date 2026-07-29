# LangChain Project Adaptation to AgentKit Runtime Sample

This sample shows how to adapt an existing LangChain project to AgentKit Runtime.

The sample project represents a user-owned LangChain travel-planning agent. Its original business entry point is `agent.py:agent`, created directly with LangChain `create_agent`. The code registers a model, a system prompt, and simple local tools with `@tool`, then accepts OpenAI messages format input.

## What This Sample Demonstrates

- A native LangChain agent built with `create_agent(model, tools, system_prompt=...)`.
- Local user-defined LangChain tools:
  - `search_travel_notes`: returns sample city attractions, food, and route notes.
  - `estimate_trip_budget`: evaluates the trip budget by city, days, and total budget.
  - `recommend_transport`: suggests a simple transport strategy.
- Migration to AgentKit Runtime without rewriting the original business entry point.

## Adapted Call Flow

Before adaptation, users can call `agent.py:agent` directly. After adaptation, AgentKit Runtime calls the same entry point through the generated `agentkit_app.py`:

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
    |
create_agent
    |-- search_travel_notes
    |-- estimate_trip_budget
    |-- recommend_transport
    `-- ChatOpenAI
```

## Directory Layout

```bash
langchain/
├── README.md
├── README_en.md
├── agent.py               # Native LangChain agent and tools
├── .env.example           # Model credential example
├── project.yaml           # Sample metadata
└── requirements.txt       # Python dependencies
```

## Local Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the native agent directly:

```bash
python agent.py
```

Configure the OpenAI-compatible chat model before running the native agent:

```bash
export MODEL_AGENT_NAME=<Your Model Name>
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=<Your Ark API Key>
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

The code uses `langchain_openai.ChatOpenAI`, so the provider is determined by that class and `MODEL_AGENT_PROVIDER` is not required. `MODEL_AGENT_API_BASE` may point to the Ark Responses endpoint. The sample normalizes it to the OpenAI-compatible API root before passing it to `ChatOpenAI`.

`VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` are not read by the native LangChain agent, but they are required when running `agentkit migrate` and `agentkit deploy`.

## Run Migration

Run this command in the current directory:

```bash
agentkit migrate . \
  --framework langchain \
  --entry agent.py:agent \
  --name migration-langchain-travel \
  --compat langserve \
  --verify
```

Arguments:

- `--framework langchain`: migrate as a LangChain Runnable-compatible entry.
- `--entry agent.py:agent`: specify the native agent entry.
- `--compat langserve`: generate LangServe-compatible routes.
- `--verify`: run basic checks after generation.

The migration command does not rewrite `agent.py`. The generated Runtime app calls the original `agent.py:agent` through `LangChainAgentkitBridge`.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by the original LangChain agent and tools.

## Example Prompt

```text
I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
```
