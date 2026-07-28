# LangGraph Migration To AgentKit Runtime Sample

## Overview

This project shows how to adapt an existing LangGraph project to AgentKit Runtime.

The sample represents a LangGraph travel-planning project. Its original entry point is `agent.py:agent`, a compiled `StateGraph`. It accepts a travel question, calls a real LLM through `create_react_agent`, and lets the ReAct agent decide when to use web search and budget-estimation tools for daily attraction, food, and transportation suggestions.

The migration does not rewrite the original business logic. `agentkit migrate` generates `agentkit_app.py` and `.agentkit/` configuration. The generated Runtime app calls the original `agent.py:agent` through `LangGraphAgentkitBridge(input_key="question")`.

## Core Features

- Shows how AgentKit Runtime calls a LangGraph compiled graph entry point.
- Uses an outer LangGraph `StateGraph` to keep the `question` input entry point.
- Uses LangGraph prebuilt `create_react_agent` to orchestrate the real LLM, web search tool, and budget-estimation tool.
- Reads model settings from environment variables and calls a real LLM node through a LangChain chat model.
- Keeps native LangGraph business code and generates the Runtime adapter with `agentkit migrate`.

## Agent Capabilities

This sample includes these Agent capabilities:

- LangGraph `StateGraph` input adaptation.
- LangGraph prebuilt ReAct agent.
- LangChain tools.
- LangChain OpenAI-compatible chat model LLM node.
- Volcengine AgentKit built-in web search tool.
- Local budget estimation business tool.

Migrated call flow:

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
        `-- create_react_agent
            |-- LangChain chat model
            |-- search_travel_web
            |   `-- veadk.tools.builtin_tools.web_search
            `-- estimate_trip_budget
```

## Directory Layout

```bash
langgraph/
├── .env.example       # Example model and Volcengine credential environment variables
├── README.md          # Chinese README
├── README_en.md       # English README
├── agent.py           # Native LangGraph graph, ReAct agent, tools, and LLM call
├── project.yaml       # Project metadata
└── requirements.txt   # Python dependencies
```

After `agentkit migrate`, the current directory contains generated `agentkit_app.py` and `.agentkit/` files. These generated files do not need to be committed with the sample source.

## Local Run

### Prerequisites

Before running web search locally or in the cloud, authorize dependent services on the [AgentKit Console authorization page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default).

### Install Dependencies

Use Python 3.10 or newer. In the sample directory, run:

```bash
pip install -r requirements.txt
```

You can also install dependencies with `uv`:

```bash
uv pip install -r requirements.txt
```

### Environment Setup

Copy `.env.example` to `.env`, then fill in the model and Volcengine AK/SK values:

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_PROVIDER=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

`MODEL_AGENT_PROVIDER`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY` are passed to the LangChain chat model. Fill them with the provider, API address, and key for your model service. If the API address ends with `/responses` or `/chat/completions`, the sample normalizes it to the API root before building the OpenAI-compatible chat model.

If the environment has no search permission, `search_travel_web` returns a search failure message and the Agent still continues through the budget and LLM nodes.

### Debugging

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
- `--entry agent.py:agent`: specify the native Graph entry point.
- `--input-key question`: write Runtime input into the `question` field.
- `--verify`: run basic checks after generation.

## AgentKit Deployment

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by `agent.py:agent` and the original LangGraph nodes.

Deployment needs the model and search environment variables:

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_PROVIDER=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

## Example Prompts

- I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
- I want to visit Hangzhou for 2 days with a 1800 RMB budget. I like West Lake, museums, and local snacks. Please plan a slow-paced route.

## Demo Output

After running an example prompt, the ReAct agent uses the real LLM to decide when to call search and budget tools, then returns a day-by-day travel plan with attractions, food, budget notes, and transportation suggestions.

```text
Beijing 3-day travel plan

Day 1: Forbidden City + Shichahai Hutongs
Day 2: Temple of Heaven + Qianmen Street
```

## FAQ

- What should I do if the search tool reports an error?

  Make sure dependent services are authorized in the AgentKit console and `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` are configured. If search fails, the sample still continues through the budget and LLM nodes.

- Why are there no model defaults in the code?

  To avoid storing endpoint, model name, or API key values in sample source, model settings must be injected through environment variables.

## License

This project is licensed under Apache 2.0 License.
