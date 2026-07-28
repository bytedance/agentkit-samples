# LangGraph Project Adaptation to AgentKit Runtime Sample

This sample shows how to adapt a LangGraph project to AgentKit Runtime.

The sample project represents an existing LangGraph travel-planning project that a user already has. Its business entry point is `agent.py:agent`, implemented as a compiled `StateGraph`. After receiving a user's travel request, it uses LangGraph orchestration to split one travel-planning task into multiple nodes: first parsing the request, then retrieving travel context and budget information, and finally summarizing daily attraction, food, and transportation suggestions.

The tools in this sample simulate tool use in a real LangGraph project:

- `search_travel_web`: simulates a tool that depends on external knowledge retrieval, and internally calls `veadk.tools.builtin_tools.web_search`
- `estimate_trip_budget`: simulates a local business calculation tool that evaluates the budget based on city, number of days, and total budget

`agent.py` is an Agent built with LangGraph. It focuses on simulating a realistic scenario where users build an agent with LangGraph:

- `StateGraph(TravelState)`: defines the shared state for travel planning and compiles it as `agent.py:agent`
- `parse_request` node: parses the city, number of days, budget, travelers, and preferences from the user's question
- `search_travel_context` node: calls `search_travel_web` and `estimate_trip_budget`, then writes external knowledge and local budget evaluation back into the graph state
- `build_final_answer` node: reads the state written by previous nodes and summarizes search context, budget evaluation, and itinerary planning
- `add_edge`: declares node execution order so the request flows through `START -> parse_request -> search_travel_context -> build_final_answer -> END`
- `InMemorySaver`: preserves session state under the same `thread_id`, simulating state continuity in a real LangGraph workflow

When adapting the project to AgentKit Runtime, you do not need to rewrite the business logic in `agent.py`. `agentkit migrate` generates `agentkit_app.py` and `.agentkit/` configuration. The generated Runtime app calls the original `agent.py:agent` through `LangGraphAgentkitBridge(input_key="question")`.

## Adapted Graph Orchestration Flow

Before adaptation, users can call `agent.py:agent` directly. After adaptation, AgentKit Runtime calls the same entry point through the generated `agentkit_app.py`. Once execution enters `agent.py:agent`, the logic is still driven by LangGraph nodes and edges:

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
    |-- parse_request
    |-- search_travel_context
    |   |-- search_travel_web
    |   |   `-- veadk.tools.builtin_tools.web_search
    |   `-- estimate_trip_budget
    `-- build_final_answer
```

## Directory Layout

```bash
langgraph/
├── README.md
├── README_EN.md
├── agent.py               # Native LangGraph graph, nodes, and tools
├── requirements.txt       # Python dependencies
└── tests                  # Local behavior tests and migration-chain regression tests
```

## Local Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the native Graph directly:

```bash
python agent.py
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

The tests directly cover the real tool-call path of `search_travel_web`.

## Search Configuration

`search_travel_web` directly uses `veadk.tools.builtin_tools.web_search`. For local or cloud execution, follow the common setup used by other samples: authorize dependent services in the [AgentKit Console authorization page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default), then configure Volcengine AK/SK:

```bash
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

If the environment has no search permission, the tool returns a search failure message. The Graph still returns a readable sample response.

## Run Migration

Run this command in the current directory:

```bash
agentkit migrate . \
  --framework langgraph \
  --entry agent.py:agent \
  --name migration-langgraph-travel \
  --input-key question \
  --verify
```

Arguments:

- `--framework langgraph`: migrate as a LangGraph compiled graph
- `--entry agent.py:agent`: specify the native Graph entry point
- `--input-key question`: write Runtime input into the `question` field
- `--verify`: run basic checks after generation

Migration generates:

```bash
langgraph/
├── agentkit_app.py
├── .agentkit/
│   ├── agentkit.yaml
│   ├── Dockerfile
│   └── migration-plan.json
└── requirements.txt
```

The migration command does not rewrite `agent.py`. The generated Runtime app calls the original `agent.py:agent` through `LangGraphAgentkitBridge(input_key="question")` and maps the AgentKit session to the LangGraph `thread_id`.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by the LangGraph nodes, checkpointer, and original tools in `agent.py:agent`.

## Example Prompt

```text
I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
```
