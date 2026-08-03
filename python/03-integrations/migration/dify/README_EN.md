# Dify Migration to AgentKit Runtime Sample

## Overview

This project demonstrates how to connect a Dify-exported workflow to AgentKit Runtime.

Dify workflows are usually not directly runnable Python projects. During migration, `agentkit migrate` submits the Dify export directory to a remote Codex Sandbox. The sandbox analyzes `workflow.yml`, optional `node_config.yml`, and the workflow structure, then generates a VeADK project that can be deployed to AgentKit Runtime.

This sample uses a Dify advanced-chat application named "专属智能客服" as the input. It focuses on the general migration flow; you can replace the input with another Dify-exported workflow for your own use case.

## Key Features

- Convert a Dify workflow into a VeADK / AgentKit Runtime project.
- Upload `node_config.yml` with the workflow to provide node runtime configuration.
- Generate deployment configuration, migration report, migration plan, and evaluation cases.
- Document unconfigured external dependencies, such as knowledge bases, plugins, and HTTP services, in the migration report instead of pretending those calls succeeded.

## Migration Flow

```text
Dify export directory
    ↓
agentkit migrate --framework dify create
    ↓
Remote Codex Sandbox
    ↓
VeADK / AgentKit Runtime project
    ├── assistant/agent.py
    ├── assistant/workflow.py
    ├── .agentkit/agentkit.yaml
    ├── convert_report.md
    ├── migration_plan.md
    └── eval/
```

## Directory Structure

```bash
dify/
├── README.md            # Chinese README
├── README_EN.md         # English README
├── .env.example         # Environment template. Copy it to .env and fill in real values.
├── dify_input/
│   ├── workflow.yml     # Workflow exported from Dify
│   └── node_config.yml  # Optional node runtime configuration
└── dify_output/         # Migration output directory, at the same level as dify_input
```

Run the following commands from the `dify/` directory. `dify_input/` is the Dify workflow input directory. `--output ../dify_output` is resolved relative to `dify_input/`, so migration artifacts are written to `dify_output/` at the same level as `dify_input/`.

## Start Remote Migration

### Check The AgentKit CLI Version

First confirm that the TypeScript version of AgentKit CLI is installed locally and that the version is at least `0.50.4`:

```bash
agentkit -v
```

If it is not installed, or if the version is lower than `0.50.4`, install the TypeScript version of AgentKit CLI with:

```bash
curl https://agentkit-cli.tos-cn-beijing.volces.com/install.sh | sh
```

### Environment Preparation

In the `dify/` directory, copy `.env.example` to `.env`, then fill in the environment variables required for migration and deployment.

AgentKit CLI automatically loads `.env` from the current working directory before running a command. You do not need to run `source .env`, so you can put environment variables directly in `.env` instead of importing them manually each time. `CODEX_MIGRATE_MODEL_API_KEY` is used by the remote Codex Sandbox migration job. `MODEL_AGENT_API_KEY` is used by the generated app at runtime.

Note: `--codex-api-key-env` and `--model-api-key-env` take environment variable names. The CLI reads the real keys from `.env`. `--codex-model`, `--model-id`, and `--model-base-url` take actual values, not environment variable names.

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

`create` submits `dify_input/` to the remote Codex Sandbox for migration. `--output ../dify_output` is resolved relative to `dify_input/`, so the final artifacts are written to `dify/dify_output/`.

```bash
cd <project_dir>/dify

agentkit migrate dify_input --framework dify create --name dify-migrate --output ../dify_output \
  --codex-model <codex model name> \
  --codex-api-key-env CODEX_MIGRATE_MODEL_API_KEY \
  --model-id <VeADK model name> \
  --model-base-url <model base_url required by VeADK> \
  --model-api-key-env MODEL_AGENT_API_KEY
```

After migration completes, `dify_output/` contains a deployable VeADK / AgentKit Runtime project. Enter that directory to run `agentkit deploy`.

## Query And Download Results

Query the job status and download the final artifacts:

```bash
agentkit migrate dify_input --framework dify status --job-id <job_id>
```

You can also use the positional argument form:

```bash
agentkit migrate dify_input --framework dify status <job_id>
```

View local migration job records:

```bash
agentkit migrate dify_input --framework dify list
```

## Optional: Local Debugging For The VeADK Project

Before deploying to AgentKit Runtime, you can locally debug the artifacts generated by migration to make sure they can run, then deploy them to AgentKit Runtime.

## AgentKit Deployment

After migration completes, enter the output directory, review `.agentkit/agentkit.yaml`, then run:

```bash
agentkit deploy
```

## Output

After migration completes, the output directory usually contains:

- A VeADK / AgentKit Runtime project that can run `agentkit deploy`.
- `.agentkit/agentkit.yaml` deployment configuration.
- `convert_report.md` migration report.
- `migration_plan.md` migration plan.
- `eval/` evaluation cases.

If the source Dify workflow depends on unconfigured knowledge bases, Dify marketplace plugins, or other external services, the migration result preserves the workflow structure and documents the degraded points in the report.

## FAQ

- Is `node_config.yml` required?

  No. It is used to provide additional node runtime configuration. If your Dify nodes depend on external configuration, such as RAG, knowledge bases, or Memory, you can provide it directly in `node_config.yml`, or add it later in the VeADK project.

- What if external dependencies cannot be restored?

  Migration does not pretend external calls succeeded. Unconfigured knowledge bases, plugins, HTTP services, and similar dependencies are documented in the migration report. You can complete the configuration later in the output project.

## License

Apache 2.0 License.
