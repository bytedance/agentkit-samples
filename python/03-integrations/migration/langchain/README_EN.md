# LangChain Agent Migration Sample

This sample migrates a native LangChain travel-planning agent to AgentKit Runtime. It shows how to keep a LangChain `Runnable`, LangChain `@tool` functions, and streaming output while using `agentkit migrate` to generate a deployable Runtime application.

## Overview

The sample uses a 3-day Beijing travel-planning scenario. Before migration, `agent.py` contains only the native LangChain agent and tools. After migration, AgentKit Runtime calls the same `agent.py:agent` entry through the generated `agentkit_app.py`.

## Key Features

- LangChain Agent: exposes `agent.py:agent` as a migratable `Runnable`
- Tool calls: uses `search_travel_web` to call `veadk.tools.builtin_tools.web_search` for travel information, and `estimate_trip_budget` to estimate the travel budget
- Input adaptation: uses `--input-key question` to map Runtime input to `{"question": "..."}`
- Streaming output: keeps `astream`, so streaming responses still work after migration
- Runtime deployment: runs `agentkit deploy` after migration to deploy to AgentKit Runtime

## Agent Flow

```text
User question
    |
AgentKit Runtime
    |
LangChainAgentkitBridge
    |
agent.py:agent
    |-- search_travel_web      # Searches attractions, reservations, food, and transportation
    `-- estimate_trip_budget   # Evaluates the travel budget
```

### Core Components

| Component | Description |
| - | - |
| **LangChain Agent** | `agent.py:agent` - `TravelPlanningRunnable`, the migration entry point |
| **Search Tool** | `search_travel_web` - LangChain `@tool` that calls `veadk.tools.builtin_tools.web_search` for travel context |
| **Budget Tool** | `estimate_trip_budget` - LangChain `@tool` that generates a budget assessment |
| **Migration Entry** | `agentkit migrate` - generates the AgentKit Runtime wrapper and deployment configuration |
| **Runtime App** | `agentkit_app.py` - generated after migration to connect the app to AgentKit Runtime |

### Code Highlights

**Agent definition**:

```python
agent = TravelPlanningRunnable()
```

**Local invocation**:

```python
agent.invoke({
    "question": "I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, and prefer a relaxed itinerary."
})
```

**Migration options**:

```bash
--entry agent.py:agent
--input-key question
```

The migration command does not rewrite the LangChain tools in `agent.py`. The generated Runtime app calls the original Runnable through `LangChainAgentkitBridge(input_key="question")`.

## Directory Layout

```bash
langchain/
├── README.md
├── README_EN.md
├── agent.py               # Native LangChain Runnable and tools
├── requirements.txt       # Python dependencies
└── tests                  # Local behavior tests and migration-chain regression tests
```

## Local Run

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Debug The Native Agent

```bash
python agent.py
```

### Run Tests

```bash
python -m unittest discover -s tests -v
```

The tests call `veadk.tools.builtin_tools.web_search` through `search_travel_web`.

## Run Migration

Run the following command in this directory:

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
- `--entry agent.py:agent`: specify the native LangChain agent entry
- `--input-key question`: write Runtime input into the `question` field
- `--compat langserve`: generate LangServe-compatible routes
- `--verify`: run basic checks after generation

After migration, the following files are generated:

```bash
langchain/
├── agentkit_app.py
├── .agentkit/
│   ├── agentkit.yaml
│   ├── Dockerfile
│   └── migration-plan.json
└── requirements.txt
```

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

`search_travel_web` uses `veadk.tools.builtin_tools.web_search`. For local or cloud execution, follow the common setup used by other samples: authorize dependent services in the AgentKit Console authorization page, then configure Volcengine AK/SK:

```bash
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

After deployment, the AgentKit Runtime entry point is `agentkit_app.py`. The business logic is still handled by `agent.py:agent` and the original LangChain tools.

## Example Prompt

```text
I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
```
