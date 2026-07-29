# LangGraph Project Adaptation To AgentKit Runtime Sample

This sample shows how to adapt an existing LangGraph project to AgentKit Runtime.

The sample project represents a user-owned LangGraph travel-planning agent. Its original business entry point is `agent.py:agent`, implemented as a compiled `StateGraph`. A graph node uses LangChain `create_agent`, registers simple local LangChain tools with `@tool`, and keeps that original graph entry point available for AgentKit migration.

## What This Sample Demonstrates

- A native LangGraph compiled graph entry point.
- A LangChain agent node built with `create_agent`.
- Local user-defined LangChain tools:
  - `search_travel_notes`: returns sample city attractions, food, and route notes.
  - `estimate_trip_budget`: evaluates the trip budget by city, days, and total budget.
  - `recommend_transport`: suggests a simple transport strategy.
- A real model created with `langchain_openai.ChatOpenAI`; the provider is determined by the `ChatOpenAI` class, so `MODEL_AGENT_PROVIDER` is not required.
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
LangGraphAgentkitBridge(input_key="question")
    |
agent.py:agent
    |
StateGraph.call_react_agent
    |
create_agent
    |-- search_travel_notes
    |-- estimate_trip_budget
    |-- recommend_transport
    `-- ChatOpenAI / local demo model
```

## Directory Layout

```bash
langgraph/
├── README.md
├── README_en.md
├── agent.py               # Native LangGraph graph, LangChain agent node, and tools
├── .env.example           # Model credentials and AgentKit command credentials
├── project.yaml           # Sample metadata
└── requirements.txt       # Dependencies split into native agent and AgentKit runtime sections
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

If no model environment variables are configured, the sample uses a local demo model so you can still inspect the migration flow. To use a real OpenAI-compatible chat model, configure:

```bash
export MODEL_AGENT_NAME=<Your Model Name>
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=<Your Ark API Key>
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

The code uses `langchain_openai.ChatOpenAI`, so the provider is determined by that class and `MODEL_AGENT_PROVIDER` is not required. `MODEL_AGENT_API_BASE` may point to the Ark Responses endpoint. The sample normalizes it to the OpenAI-compatible API root before passing it to `ChatOpenAI`.

`VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` are not read by the native LangGraph agent business code, but they are required when running `agentkit migrate` and `agentkit deploy`.

## Run Migration

Run this command in the current directory:

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
- `--entry agent.py:agent`: specify the native graph entry point.
- `--input-key question`: write Runtime input into the `question` field.
- `--verify`: run basic checks after generation.

The migration command does not rewrite `agent.py`. The generated Runtime app calls the original `agent.py:agent` through `LangGraphAgentkitBridge(input_key="question")`.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by the original LangGraph graph and local tools.

## Example Prompt

```text
I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
```
