# LangChain Project Adaptation to AgentKit Runtime Sample

This sample shows how to adapt a LangChain project to AgentKit Runtime.

The sample project represents an existing LangChain travel-planning project that a user already has. Its business entry point is `agent.py:agent`, implemented as `TravelPlanningRunnable`. It takes a user's travel request, parses the city, number of days, budget, travelers, and interests, calls tools to collect search and budget context, then uses LiteLLM to call a real LLM node for daily attraction, food, and transportation suggestions.

The tools in this sample simulate tool use in a real LangChain project:

- `search_travel_web`: simulates a tool that depends on external knowledge retrieval, and internally calls `veadk.tools.builtin_tools.web_search`
- `estimate_trip_budget`: simulates a local business calculation tool that evaluates the budget based on city, number of days, and total budget

`agent.py` is a LangChain-based agent. It uses `Runnable` to define the callable entry point, `@tool` to declare tool functions, and calls `veadk.tools.builtin_tools.web_search` inside `search_travel_web` to retrieve external knowledge. The related dependencies are:

```python
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from veadk.tools.builtin_tools.web_search import web_search as builtin_web_search
```

- `TravelPlanningRunnable(Runnable)`: implements the native LangChain agent and exposes it as `agent.py:agent` for migration
- `@tool`: declares `search_travel_web` and `estimate_trip_budget` as LangChain tools
- `model_agent`: creates a LiteLLM-backed model node and reads `MODEL_AGENT_NAME`, `MODEL_AGENT_PROVIDER`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY`
- `builtin_web_search`: called by `search_travel_web` to simulate a real project tool that needs external knowledge retrieval

When adapting the project to AgentKit Runtime, you do not need to rewrite the business logic in `agent.py`. `agentkit migrate` generates `agentkit_app.py` and `.agentkit/` configuration. The generated Runtime app calls the original `agent.py:agent` through `LangChainAgentkitBridge(input_key="question")`.

## Adapted Call Flow

Before adaptation, users can call `agent.py:agent` directly. After adaptation, AgentKit Runtime calls the same entry point through the generated `agentkit_app.py`:

```text
User question
    |
AgentKit Runtime
    |
agentkit_app.py
    |
LangChainAgentkitBridge(input_key="question")
    |
agent.py:agent  # TravelPlanningRunnable
    |-- search_travel_web
    |   `-- veadk.tools.builtin_tools.web_search
    |-- estimate_trip_budget
    `-- model_agent
        `-- litellm.completion
```

## Directory Layout

```bash
langchain/
├── README.md
├── README_en.md
├── agent.py               # Native LangChain Runnable and tools
├── .env.example           # Model and Volcengine credential examples
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

## Model Configuration

`agent.py` reads model settings from environment variables and uses LiteLLM to call the model:

```bash
export MODEL_AGENT_NAME=<Your Model Name>
export MODEL_AGENT_PROVIDER=openai
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=<Your Ark API Key>
```

For consistency with other VeADK/AgentKit samples, `MODEL_AGENT_API_BASE` can use the Ark Responses endpoint. Before calling LiteLLM, the sample normalizes it to the OpenAI-compatible API root `https://ark.cn-beijing.volces.com/api/v3`.

## Search Configuration

`search_travel_web` directly uses `veadk.tools.builtin_tools.web_search`. For local or cloud execution, follow the common setup used by other samples: authorize dependent services in the [AgentKit Console authorization page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default), then configure Volcengine AK/SK:

```bash
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

If the environment has no search permission, the tool returns a search failure message. The agent still returns a readable sample response.

## Run Migration

Run this command in the current directory:

```bash
agentkit migrate . \
  --framework langchain \
  --entry agent.py:agent \
  --name migration-langchain-travel \
  --input-key question \
  --compat langserve \
  --verify
```

Arguments:

- `--framework langchain`: migrate as a LangChain Runnable
- `--entry agent.py:agent`: specify the native agent entry
- `--input-key question`: write Runtime input into the `question` field
- `--compat langserve`: generate LangServe-compatible routes
- `--verify`: run basic checks after generation

Migration generates:

```bash
langchain/
├── agentkit_app.py
├── .agentkit/
│   ├── agentkit.yaml
│   ├── Dockerfile
│   └── migration-plan.json
└── requirements.txt
```

The migration command does not rewrite `agent.py`. The generated Runtime app calls the original `agent.py:agent` through `LangChainAgentkitBridge(input_key="question")`.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by `agent.py:agent` and the original LangChain tools.

Deployment needs both model and search environment variables:

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_PROVIDER=openai
MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

## Example Prompt

```text
I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
```
