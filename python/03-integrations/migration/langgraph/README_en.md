# LangGraph Migration to AgentKit Runtime Sample

## Overview

This sample shows how to connect an existing LangGraph project to AgentKit Runtime.

This sample uses `agent.py` to simulate an existing LangGraph travel-planning project and shows how to migrate it to AgentKit Runtime.

This demo guides you through adapting the LangGraph project, generating artifacts that can be deployed to AgentKit Runtime, and completing the deployment.

## Key Features

- Shows how an existing LangGraph project connects to AgentKit Runtime.
- Uses `@tool` to declare local travel-note search, budget estimation, and transportation recommendation tools.
- Preserves the native LangGraph business code and generates Runtime entry files and configuration through `agentkit migrate`.

## Agent Capabilities

This sample includes the following local tools:

- `search_travel_notes`: searches built-in city travel notes.
- `estimate_trip_budget`: estimates whether the budget is sufficient by city, days, and total budget.
- `recommend_transport`: recommends transportation by city and traveler type.

After migration, the call flow is:

```text
User question
    ↓
AgentKit Runtime
    ↓
agentkit_app.py
    ↓
LangGraphAgentkitBridge
    ↓
agent.py:agent
    ├── LangGraph graph
    ├── search_travel_notes
    ├── estimate_trip_budget
    └── recommend_transport
```

## Directory Structure

```bash
langgraph/
├── .env.example       # Model configuration environment variable example
├── README.md          # Chinese README
├── README_en.md       # English README
├── agent.py           # Native LangGraph graph, ReAct Agent, and local tools
└── requirements.txt   # Python dependencies
```

## Local Run

### Check AgentKit CLI Version

First make sure the TypeScript version of AgentKit CLI is installed and the version is not lower than `0.51.1`:

```bash
agentkit -v
```

or

```bash
ak -v
```

If it is not installed, or the version is lower than `0.51.1`, install the TypeScript version of AgentKit CLI with:

```bash
curl https://agentkit-cli.tos-cn-beijing.volces.com/install.sh | sh
```

> Use the TypeScript AgentKit CLI entrypoint `ak` for migration commands to avoid possible `agentkit` command conflicts from Python `uv` environments or the `agentkit-python-sdk` package. `ak` is configured automatically by the installer; no extra setup is required.

### Install Dependencies

Make sure the Python version is 3.10 or later. From this sample directory, run:

```bash
pip install -r requirements.txt
```

You can also use `uv` to install dependencies:

```bash
uv pip install -r requirements.txt
```

### Environment Preparation

Copy `.env.example` to `.env`, then fill in the required model configuration in `.env`:

```text
MODEL_AGENT_NAME=<model-name>
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<api-key>
```

This sample first uses `langchain_openai.ChatOpenAI` to create the model, so `MODEL_AGENT_PROVIDER` is not required. Make sure your model endpoint supports the OpenAI format. If model configuration is not provided, `python agent.py` uses the built-in local sample model so you can verify that the native LangGraph entry is runnable.

If you need to deploy the generated artifacts to AgentKit Runtime, write the corresponding platform account configuration into `.env`.

Volcengine China:

```text
VOLCENGINE_ACCESS_KEY=<access-key>
VOLCENGINE_SECRET_KEY=<secret-key>
```

BytePlus overseas AgentKit:

```text
BYTEPLUS_ACCESS_KEY=<access-key>
BYTEPLUS_SECRET_KEY=<secret-key>
CLOUD_PROVIDER=byteplus
BYTEPLUS_REGION=ap-southeast-1
```

### Pre-check

Before migration, first make sure the original LangGraph project is healthy and runnable:

```bash
python agent.py
```

This command calls `agent.py:agent`, sends a fixed travel question to the LangGraph graph, and outputs a readable travel-planning result.

### Run The Migration Command

After confirming that the original project is executable, run the migration command to generate Runtime entry files and configuration:

```bash
agentkit migrate . \
  --framework langgraph \
  --entry agent.py:agent \
  --name migration-langgraph-travel \
  --input-key question \
  --verify
```

Equivalent `ak` command:

```bash
ak migrate . \
  --framework langgraph \
  --entry agent.py:agent \
  --name migration-langgraph-travel \
  --input-key question \
  --verify
```

Arguments:

- `--framework langgraph`: migrate as a LangGraph graph.
- `--entry agent.py:agent`: specify the native LangGraph entry.
- `--input-key question`: write Runtime input into the `question` field.
- `--verify`: run basic checks after generation.

After the command succeeds, it generates entry files and configuration that can be deployed to AgentKit Runtime.
The migration process does not rewrite the original LangGraph `agent.py`.

## deploy to Agentkit

If you want to deploy the generated artifacts to AgentKit Runtime, run:

```bash
agentkit release
```

Equivalent `ak` command:

```bash
ak release
```

After deployment, you can find the deployed project in AgentKit Runtime on the AgentKit platform.

## Example Prompts

- I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
- I want to visit Chengdu for 2 days with a budget of 2000 RMB. I like food and city neighborhoods. Please arrange a relaxed route.

## Example Output

After running an example prompt, the Agent calls local travel notes, budget, and transportation tools through LangGraph nodes, then outputs a day-by-day travel plan including attraction arrangements, dining suggestions, budget judgment, and transportation suggestions.

```text
Beijing 3-day travel plan (sample model output)

Day 1: Palace Museum + Shichahai hutongs
Day 2: Temple of Heaven Park + Qianmen area
```

## FAQ

- Does the migration command rewrite the original `agent.py`?

  No. The migration command adds Runtime entry files, while the original LangGraph business entry remains unchanged.

## License

This project is licensed under the Apache 2.0 License.
