# Google ADK Project Adaptation to AgentKit Runtime Sample

This sample shows how to adapt an existing Google ADK project to AgentKit Runtime.

The sample represents a user-owned Google ADK travel-planning project. Its native business entry point is `agent.py:root_agent`, implemented as a `google.adk.agents.Agent`. The code registers an OpenAI-compatible Ark model, instructions, and simple local tools with the native Google ADK `Agent`.

The code also exposes `agent.py:agent` as an alias for `root_agent`, but the migration command below uses the common Google ADK `root_agent` entry point.

## What This Sample Demonstrates

- A native Google ADK `Agent` entry point that can be wrapped by AgentKit Runtime.
- Local user-defined Python function tools:
  - `search_travel_notes`: returns sample city attractions, food, and route notes.
  - `estimate_trip_budget`: evaluates the trip budget by city, days, and total budget.
  - `recommend_transport`: suggests a simple transport strategy.
- Migration to AgentKit Runtime without rewriting the original business entry point.
- OpenAI-compatible Ark model settings shared with the other migration samples.
- No `MODEL_AGENT_PROVIDER` setting.

## Adapted Call Flow

Before adaptation, users can reference `agent.py:root_agent` directly. After adaptation, AgentKit Runtime calls the same entry point through the generated `agentkit_app.py`:

```text
User question
    |
AgentKit Runtime
    |
agentkit_app.py
    |
AgentkitAgentServerApp
    |
agent.py:root_agent
    |-- search_travel_notes
    |-- estimate_trip_budget
    `-- recommend_transport
```

## Directory Layout

```bash
google_adk/
├── README.md
├── README_en.md
├── agent.py               # Native Google ADK Agent and local tools
├── .env.example           # Ark model variable names
├── project.yaml           # Sample metadata
└── requirements.txt       # Split into native ADK and AgentKit migration runtime dependencies
```

`agentkit migrate` generates `agentkit_app.py` and `.agentkit/` in this directory. Those generated files are intentionally not committed in the sample source.

## Local Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the native project file directly:

```bash
python agent.py
```

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

This command calls `agent.py:root_agent` through the ADK `Runner`, sends the fixed prompt `我想去北京玩3天`, and uses the configured OpenAI-compatible Ark model for one real agent turn.

The native code uses Google ADK `Agent` and ADK `OpenAILlm`. `MODEL_AGENT_API_BASE` may point to the Ark Responses endpoint; the sample normalizes it to the OpenAI-compatible API root before passing it to the OpenAI SDK. `MODEL_AGENT_PROVIDER` is not required by this sample.

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

Account credentials are not written to `.env.example` or `.env`, and are not read by the native Google ADK business agent.

## Run Migration

Run this command in the current directory:

```bash
agentkit migrate . \
  --framework adk \
  --entry agent.py:root_agent \
  --name migration-google-adk-travel \
  --verify
```

Arguments:

- `--framework adk`: migrate as a Google ADK Agent entry.
- `--entry agent.py:root_agent`: specify the native Google ADK agent entry.
- `--name migration-google-adk-travel`: set the generated AgentKit app name.
- `--verify`: run basic checks after generation.

Google ADK migration does not need `--input-key`. The generated wrapper uses `AgentkitAgentServerApp` and preserves the original `agent.py`.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by the original `agent.py:root_agent` and local tools.

Deployment needs model env vars in the deployment environment. Export account credentials with the Volcengine or BytePlus block above:

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

## Example Prompt

```text
I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
```
