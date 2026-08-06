# Any Generic Migration to AgentKit Runtime Sample

## Overview

This project demonstrates how to use `--framework any` to migrate a Python agent project that is not explicitly adapted yet, has an unfixed structure, or needs automated migration analysis into a VeADK project that can be deployed to AgentKit Runtime.

AgentKit Runtime natively supports LangChain, LangGraph, Strands, Google ADK, and projects built on Bedrock AgentCore Runtime. For Python agent projects that are not explicitly adapted yet, you can use `agentkit migrate --framework any create` to submit the source project to a remote Codex Sandbox. The sandbox analyzes the project structure and generates an AgentKit Runtime project that can run on AgentKit Runtime.

This sample uses a Strands travel-planning agent as the input. It uses `--framework any` to show how generic migration can automatically understand the project structure.

## Key Features

- Submit an existing Python agent project directory to a remote Codex Sandbox for migration.
- Convert the source project into a VeADK / AgentKit Runtime project.
- Generate deployable configuration and runtime code, then continue with `agentkit release` after migration.
- Document external dependencies or runtime configuration that cannot be restored automatically instead of pretending those calls succeeded.

## Source Input

The input directory is `any_input/`, which contains a travel-planning agent:

- Entry code: `any_input/agent.py`
- Framework: Strands `Agent`
- Tools: city note search, budget estimation, and transportation recommendation
- Model configuration: when `MODEL_AGENT_NAME` and `MODEL_AGENT_API_KEY` are configured, the agent calls an OpenAI-compatible model; otherwise it uses `LocalTravelModel` for local preflight checks.
- Migration goal: let the Codex Sandbox understand the project structure automatically and generate a VeADK / AgentKit Runtime output project

## Migration Flow

```text
Python agent project
    ↓
agentkit migrate --framework any create
    ↓
Remote Codex Sandbox
    ↓
VeADK / AgentKit Runtime project
    ├── .agentkit/agentkit.yaml
    └── Runtime code and other migration artifacts
```

## Directory Structure

```bash
any/
├── .env.example       # Environment variable example
├── README.md          # Chinese README
├── README_EN.md       # English README
├── requirements.txt   # Python dependencies
├── any_input/
│   └── agent.py       # Native Strands travel-planning agent
└── any_output/        # Migration output directory, at the same level as any_input
```

Run the following commands from the `any/` directory. `any_input/` is the source project input directory. `--output ../any_output` is resolved relative to `any_input/`, so migration artifacts are written to `any_output/` at the same level as `any_input/`.

## Start Remote Migration

### Check The AgentKit CLI Version

First confirm that the TypeScript version of AgentKit CLI is installed locally and that the version is at least `0.51.1`:

```bash
agentkit -v
```

or

```bash
ak -v
```

If it is not installed, or if the version is lower than `0.51.1`, install the TypeScript version of AgentKit CLI with:

```bash
curl https://agentkit-cli.tos-cn-beijing.volces.com/install.sh | sh
```

> Use the TypeScript AgentKit CLI entrypoint `ak` for migration commands to avoid possible `agentkit` command conflicts from Python `uv` environments or the `agentkit-python-sdk` package. `ak` is configured automatically by the installer; no extra setup is required.

### Environment Preparation

In the `any/` directory, copy `.env.example` to `.env`, then fill in the environment variables required for migration and deployment.

AgentKit CLI automatically loads `.env` from the current working directory before running a command. You do not need to run `source .env`, so you can put environment variables directly in `.env` instead of importing them manually each time. `CODEX_MIGRATE_MODEL_API_KEY` is used by the remote Codex Sandbox migration job. `MODEL_AGENT_API_KEY` is used by the generated app at runtime.

Note: `--codex-api-key-env` and `--model-api-key-env` take environment variable names; the CLI reads the real keys from `.env`. `--codex-model`, `--model-id`, and `--model-base-url` take actual values, not environment variable names.

Volcengine:

```bash
VOLCENGINE_ACCESS_KEY=""
VOLCENGINE_SECRET_KEY=""

CODEX_MODEL_AGENT_NAME=""
CODEX_MIGRATE_MODEL_API_KEY=""

MODEL_AGENT_NAME=""
MODEL_AGENT_API_BASE=""
MODEL_AGENT_API_KEY=""
```

BytePlus:

If you use BytePlus, provide the BytePlus AK/SK and model connection configuration. Replace the Volcengine account variables in `.env` with `BYTEPLUS_ACCESS_KEY` / `BYTEPLUS_SECRET_KEY`, then set `CLOUD_PROVIDER=byteplus` and `BYTEPLUS_REGION`.

```bash
BYTEPLUS_ACCESS_KEY=""
BYTEPLUS_SECRET_KEY=""
CLOUD_PROVIDER=byteplus
BYTEPLUS_REGION=ap-southeast-1

CODEX_MODEL_AGENT_NAME=""
CODEX_MIGRATE_MODEL_API_KEY=""

MODEL_AGENT_NAME=""
MODEL_AGENT_API_BASE=""
MODEL_AGENT_API_KEY=""
```

### Create A Migration Job

`create` submits `any_input/` to the remote Codex Sandbox for migration. `--output ../any_output` is resolved relative to `any_input/`, so the final artifacts are written to `any/any_output/`.

```bash
cd <project_dir>/any

agentkit migrate any_input --framework any create --name any-test --output ../any_output \
  --codex-model <codex model name> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK model name> \
  --model-base-url <model base_url required by VeADK> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

Equivalent `ak` command:

```bash
cd <project_dir>/any

ak migrate any_input --framework any create --name any-test --output ../any_output \
  --codex-model <codex model name> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK model name> \
  --model-base-url <model base_url required by VeADK> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

After migration completes, `any_output/` contains a complete VeADK / AgentKit Runtime project. Enter that directory to run `agentkit release`.

## Query And Download Results

Query the job status and download the final artifacts:

```bash
agentkit migrate any_input --framework any status --job-id <job_id>
```

Equivalent `ak` command:

```bash
ak migrate any_input --framework any status --job-id <job_id>
```

You can also use the positional argument form:

```bash
agentkit migrate any_input --framework any status <job_id>
```

Equivalent `ak` command:

```bash
ak migrate any_input --framework any status <job_id>
```

View local migration job records:

```bash
agentkit migrate any_input --framework any list
```

Equivalent `ak` command:

```bash
ak migrate any_input --framework any list
```

## Optional: Local Debugging For The VeADK Project

Before deploying to AgentKit Runtime, you can locally debug the artifacts generated by migration to make sure they can run, then deploy them to AgentKit Runtime.

## deploy to Agentkit

After migration completes, enter the output directory, review `.agentkit/agentkit.yaml`, then run:

```bash
agentkit release
```

Equivalent `ak` command:

```bash
ak release
```

## Output

After migration completes, the output directory usually contains:

- A VeADK / AgentKit Runtime project that can run `agentkit release`.
- `.agentkit/agentkit.yaml` deployment configuration.
- Migration notes, runtime code, and required dependency files.

The exact files depend on the actual migration output. If the source project depends on unconfigured external services, the migration result preserves the recoverable project structure and documents the configuration that needs to be completed later.

## Example Inputs

- I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
- I want to visit Xi'an for 2 days with a budget of 1800 RMB. I like historical sites and local snacks. Please arrange a relaxed route.

## Example Output

After running an example prompt, the agent combines local city notes, budget evaluation, and transportation suggestions to produce a day-by-day travel plan.

```text
Beijing 3-day travel plan (sample model output)

Requirement summary: traveling with parents or elders, with routes arranged using local notes, budget evaluation, and transportation suggestions.
Budget suggestion: with a total budget of 3000 RMB for 3 days in Beijing, the average is about 1000 RMB per person per day; the budget is relatively comfortable.
```

## Arguments

- `--framework any`: use generic agentic migration.
- `create`: create a remote migration job.
- `status`: query the job and download results.
- `list`: view local `any_input/.agentkit/migrate/jobs/` records.
- `--codex-model`: Codex Sandbox migration model name; pass the actual model name.
- `--codex-api-key-env`: environment variable name that holds the Codex Sandbox model key.
- `--model-id`: runtime model name for the generated app; pass the actual model name.
- `--model-base-url`: OpenAI-compatible runtime model base URL for the generated app; pass the actual base URL.
- `--model-api-key-env`: environment variable name that holds the runtime model key; defaults to `MODEL_AGENT_API_KEY` when omitted.

## FAQ

- Does the migration command rewrite `any_input/agent.py`?

  No. The migration job uploads the source project as input for analysis and writes the generated AgentKit Runtime project to the directory specified by `--output`.

## License

Apache 2.0 License.
