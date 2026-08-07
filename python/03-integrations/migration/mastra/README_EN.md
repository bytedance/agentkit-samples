# Mastra Migration to AgentKit Runtime Sample

## Overview

This example demonstrates how to use AgentKit Migration with a remote Codex Sandbox to migrate a project built with Mastra into a VeADK project that can be deployed to the AgentKit Runtime.

Mastra primarily uses TypeScript as its development language, with agents defined and implemented using Mastra’s `@mastra/core/agent` module. In most Mastra projects, the core agent-related logic—including agent definitions, tools, and related configurations—is typically located under the `src/mastra` directory.

Therefore, for most Mastra projects that follow the standard project structure, you can use the `src/mastra` directory directly as the input to `agentkit migrate`. The Codex Sandbox analyzes the agent semantics and tool definitions in the directory and migrates them into the corresponding VeADK project.

## Key Features

- Submit the `src/mastra` contents of a Mastra project to the AgentKit Codex Sandbox for migration.
- Convert a simple Mastra agent + tools project into a VeADK / AgentKit Runtime project.
- Generate deployable configuration and runtime code. After migration completes, you can run `agentkit release` to publish the agent to AgentKit Runtime.

## Source Input

The source input for this sample is a simple Mastra agent + tools project, used as the input for AgentKit Codex Sandbox migration.

## Migration Flow

The migration process has four steps:

1. Prepare the Mastra `src/mastra` contents as input.
2. Run `agentkit migrate any_input --framework any create` to create a migration job.
3. The remote Codex Sandbox analyzes the Mastra agent, tools, and registration relationships.
4. Generate a VeADK / AgentKit Runtime project, including `.agentkit/agentkit.yaml`, runtime code, and other migration artifacts.

## Directory Structure

| Path | Description |
| --- | --- |
| `.env.example` | Environment variable example |
| `README.md` | Chinese documentation |
| `README_EN.md` | English documentation |
| `any_input/mastra/index.ts` | Mastra registration entrypoint |
| `any_input/mastra/agents/agent.ts` | Mastra agent definition |
| `any_input/mastra/tools/beijing-travel-search.ts` | Registered Beijing travel mock search tool |
| `any_input/mastra/tools/schedule-tools.ts` | Unregistered sample tool code |
| `any_output/` | Output directory written after migration, at the same level as `any_input/` |

Run all commands below from the `mastra/` directory. `any_input/` is the source project input directory. `--output ../any_output` is resolved relative to `any_input/`, so migration artifacts are written to the `any_output/` directory at the same level as `any_input/`.

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

In the `mastra/` directory, copy `.env.example` to `.env`, then fill in the environment variables required for migration and deployment.

AgentKit CLI automatically loads `.env` from the current working directory before running a command. You do not need to run `source .env`, so you can put environment variables directly in `.env` instead of importing them manually each time. `CODEX_MIGRATE_MODEL_API_KEY` is used by the remote Codex Sandbox migration job. `MODEL_AGENT_API_KEY` is used by the generated app at runtime.

Note: `--codex-api-key-env` and `--model-api-key-env` take environment variable names; the CLI reads the real keys from `.env`. `--codex-model`, `--model-id`, and `--model-base-url` take actual values.

Volcengine:

```bash
VOLCENGINE_ACCESS_KEY=""
VOLCENGINE_SECRET_KEY=""

CODEX_MODEL_AGENT_NAME=""
CODEX_MIGRATE_MODEL_API_KEY=""

MODEL_AGENT_NAME=""
MODEL_AGENT_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
MODEL_AGENT_API_KEY=""
```

BytePlus:

If you use BytePlus, provide the BytePlus AK/SK and model connection configuration. When using BytePlus, replace the Volcengine account variables in `.env` with `BYTEPLUS_ACCESS_KEY` / `BYTEPLUS_SECRET_KEY`, then set `CLOUD_PROVIDER=byteplus` and `BYTEPLUS_REGION`.

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

`create` submits `any_input/` to the remote Codex Sandbox for migration. `--output ../any_output` is resolved relative to `any_input/`, so the final artifacts are written to `mastra/any_output/`.

```bash
cd <project_dir>/mastra

agentkit migrate any_input --framework any create --name mastra-test --output ../any_output \
  --codex-model <Codex model name> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK model name> \
  --model-base-url <model base_url required by VeADK> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

Equivalent `ak` command:

```bash
cd <project_dir>/mastra

ak migrate any_input --framework any create --name mastra-test --output ../any_output \
  --codex-model <Codex model name> \
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

Before deploying to AgentKit Runtime, you can locally debug the migrated artifacts to make sure they can run, then deploy them to AgentKit Runtime.

## AgentKit Deployment

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

- A VeADK / AgentKit Runtime project that can directly run `agentkit release`.
- `.agentkit/agentkit.yaml` deployment configuration.
- Migration notes, runtime code, and required dependency files.

The exact files depend on the actual migration output. If the source project depends on unconfigured external services, the migration result preserves the recoverable project structure and documents the configuration that needs to be completed later.

## Example Prompts

- I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
- I want to visit Japan for 5 days. Help me plan a relaxed itinerary.

## Result Preview

After running an example prompt, the agent combines the agent instructions and tool logic migrated from Mastra `src/mastra` and outputs a day-by-day travel plan.

```text
Beijing 3-Day Travel Plan

The following content is compiled from built-in Beijing travel mock static materials. It is not a real-time search result. Before departure, verify ticketing, reservations, weather, transportation, and pricing information yourself.
```

## Arguments

- `--framework any`: use generic agentic migration.
- `create`: create a remote migration job.
- `status`: query the job and download results.
- `list`: view local `any_input/.agentkit/migrate/jobs/` records.
- `--codex-model`: model used by the remote Codex Sandbox; pass the actual model name.
- `--codex-api-key-env`: environment variable name from which the remote Codex Sandbox reads the model key.
- `--model-id`: runtime model used by the generated project; pass the actual model name.
- `--model-base-url`: OpenAI-compatible endpoint for the runtime model; pass the actual base URL.
- `--model-api-key-env`: environment variable name for the runtime model key; defaults to `MODEL_AGENT_API_KEY` when omitted.

## FAQ

- Does the migration command rewrite `any_input/`?

  No. The migration job uploads the source project as input for analysis and writes the generated AgentKit Runtime project to the directory specified by `--output`.

- Is only providing `src/mastra` enough?

  For a simple Mastra agent + tools project like this sample, yes. The information required for Codex migration is already contained in `src/mastra`, including the agent definition, registration entrypoint, tool definitions, tool schemas, tool execution logic, and the bindings between the agent and tools. For more complex Mastra projects that depend on shared modules, asset files, or additional runtime configuration outside `src/mastra`, you need to provide that context as well.

## License

This project is licensed under the Apache 2.0 License.
