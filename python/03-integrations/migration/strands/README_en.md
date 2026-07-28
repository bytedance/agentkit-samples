# Strands Project Adaptation to AgentKit Runtime Sample

This sample shows how to adapt a Strands project to AgentKit Runtime.

The sample project simulates an existing Strands travel-planning project. Its business entry point is `agent.py:build_agent`, which creates and returns a Strands `Agent`. After receiving a user's travel request, the Agent uses the Strands Agent + tools execution model to call web search, budget estimation, and a real LLM for daily attraction, food, and transportation suggestions.

The tools in this sample simulate tool use in a real Strands project:

- `search_travel_web`: simulates a tool that depends on external knowledge retrieval, and internally calls `veadk.tools.builtin_tools.web_search`
- `estimate_trip_budget`: simulates a local business calculation tool that evaluates the budget based on city, number of days, and total budget

`agent.py` is an Agent built with Strands. It focuses on common native Strands project patterns for Agent factories and tool registration:

- `build_agent()`: creates a native Strands `Agent` and exposes it as `agent.py:build_agent` for the migration command
- `TRAVEL_TOOLS`: centrally registers `search_travel_web` and `estimate_trip_budget`
- `@tool`: declares regular Python functions as Strands tools so the Agent can use them through tool calls
- `search_travel_web`: calls `veadk.tools.builtin_tools.web_search` inside the tool, simulating a real project's dependency on external knowledge retrieval
- `estimate_trip_budget`: preserves local business calculation logic, simulating an internal tool in a real project
- `build_model()`: creates a real Strands `OpenAIModel` from `MODEL_AGENT_NAME`, `MODEL_AGENT_PROVIDER`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY`

When adapting the project to AgentKit Runtime, you do not need to rewrite the business logic in `agent.py`. `agentkit migrate` generates `agentkit_app.py` and `.agentkit/` configuration. The generated Runtime app calls the original `agent.py:build_agent` through `StrandsAgentkitBridge(agent_factory=True)`.

## Adapted Agent Call Flow

Before adaptation, users can directly call `agent.py:build_agent` to create the Strands Agent. After adaptation, AgentKit Runtime calls the same entry point through the generated `agentkit_app.py`. Once execution enters `agent.py:build_agent`, the business logic is still handled by the Strands `Agent` and the registered tools:

```text
User question
    |
AgentKit Runtime
    |
agentkit_app.py
    |
StrandsAgentkitBridge(agent_factory=True)
    |
agent.py:build_agent
    |
Strands Agent
    |-- OpenAIModel
    |-- search_travel_web
    |   `-- veadk.tools.builtin_tools.web_search
    `-- estimate_trip_budget
```

## Directory Layout

```bash
strands/
├── README.md
├── README_en.md
├── .env.example           # Example model and Volcengine credential environment variables
├── agent.py               # Native Strands Agent factory, tools, and LLM config
├── requirements.txt       # Python dependencies
```

## Local Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the native Agent directly:

```bash
python agent.py
```

Configure model and Volcengine AK/SK values:

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_PROVIDER=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

`MODEL_AGENT_PROVIDER` should currently be set to `openai`. `MODEL_AGENT_API_BASE` may use the Ark Responses endpoint; before passing it to Strands `OpenAIModel`, the sample normalizes it to an OpenAI-compatible API root.

## Search Configuration

`search_travel_web` directly uses `veadk.tools.builtin_tools.web_search`. For local or cloud execution, follow the common setup used by other samples: authorize dependent services in the [AgentKit Console authorization page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default), then configure Volcengine AK/SK:

```bash
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

If the environment has no search permission, the tool returns a search failure message. The Agent still continues through the budget and LLM nodes.

## Run Migration

Run this command in the current directory:

```bash
agentkit migrate . \
  --framework strands \
  --entry agent.py:build_agent \
  --name migration-strands-travel \
  --verify \
  --force
```

Arguments:

- `--framework strands`: migrate as a Strands Agent
- `--entry agent.py:build_agent`: specify the native Strands Agent factory entry point
- `--verify`: run basic checks after generation

Migration generates:

```bash
strands/
├── agentkit_app.py
├── .agentkit/
│   ├── agentkit.yaml
│   ├── Dockerfile
│   └── migration-plan.json
└── requirements.txt
```

The migration command does not rewrite `agent.py`. The generated Runtime app calls the original `agent.py:build_agent` through `StrandsAgentkitBridge(agent_factory=True)`.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by the Strands Agent created by `agent.py:build_agent` and the original tools.

Deployment needs the model and search environment variables:

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_PROVIDER=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

## Example Prompt

```text
I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
```
