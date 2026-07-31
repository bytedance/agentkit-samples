# Dify Migration to AgentKit Runtime Sample

## Overview

AgentKit Runtime natively supports mainstream agent frameworks, including LangChain, LangGraph, Strands, Google ADK, and projects built on Bedrock AgentCore Runtime. For workflows exported from Dify, you can use `agentkit migrate` to submit the workflow input to a remote Codex sandbox and generate a VeADK / AgentKit Runtime project.

This directory demonstrates the migration flow for a Dify advanced-chat application: start from the exported Dify workflow and generate an AgentKit Runtime project that can directly run `agentkit deploy`.

## Source Input

The input is a Dify advanced-chat application named "专属智能客服".

The source directory should contain:

- `workflow.yml` or `workflow.yaml`: the workflow exported from Dify.
- `node_config.yml`: optional. Put it in the source directory and upload it together with the workflow to define runtime configuration for workflow nodes.

## Environment Variables

Prepare AgentKit account credentials and model configuration first. Do not write real secrets into the README, `.env`, or the code repository.

Volcengine China:

```bash
# AgentKit
export VOLCENGINE_ACCESS_KEY=""
export VOLCENGINE_SECRET_KEY=""

# Ark model
export MODEL_AGENT_NAME=""
export MODEL_AGENT_PROVIDER="openai"
export MODEL_AGENT_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
export MODEL_AGENT_API_KEY=""

# `AGENTKIT_MIGRATE_MODEL_API_KEY` is the model key used by the remote Codex sandbox.
export AGENTKIT_MIGRATE_MODEL_API_KEY=""
```

BytePlus:

```bash
# BytePlus model
export MODEL_AGENT_NAME=""
export MODEL_AGENT_PROVIDER="openai"
export MODEL_AGENT_API_BASE="https://ark.ap-southeast.bytepluses.com/api/v3/"
export MODEL_AGENT_API_KEY=""
# `AGENTKIT_MIGRATE_MODEL_API_KEY` is the model key used by the remote Codex sandbox.
export AGENTKIT_MIGRATE_MODEL_API_KEY=""

# BytePlus AgentKit AKSK
export BYTEPLUS_ACCESS_KEY=""
export BYTEPLUS_SECRET_KEY=""
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_REGION=ap-southeast-1
```

## Create A Migration Job

`create` starts a real remote migration job. Run it only after confirming the environment variables and input directory.

```bash
cd <project_dir>
source .venv/bin/activate
command -v agentkit

cd dify/dify_input
# Use the current directory as the working directory.
agentkit migrate . --framework dify create --name dify-migrate --output ../dify_output
```

This command uses the Dify workflow in the current directory as the source input and writes the final artifacts to the directory specified by `--output`.

## Query And Download Results

Query the job status and download the final artifacts:

```bash
agentkit migrate . --framework dify status --job-id <job_id>
```

You can also use the positional argument form:

```bash
agentkit migrate . --framework dify status <job_id>
```

View local migration job records:

```bash
agentkit migrate . --framework dify list
```

## Output

After migration completes, the output directory contains:

- A VeADK / AgentKit Runtime project that can directly run `agentkit deploy`.
- `.agentkit/agentkit.yaml` deployment configuration.
- `convert_report.md` migration report.
- `migration_plan.md` migration plan.
- `eval/` evaluation cases.

Some external dependencies in the current Dify input cannot be restored directly, such as an unconfigured knowledge base and Dify marketplace plugins. The migration result preserves the workflow structure and clearly documents these degradation points in the report instead of pretending that external calls succeeded.

## Deploy

Enter the migration output directory and review `.agentkit/agentkit.yaml`; then you can run `agentkit deploy`. Continue using the AgentKit account credentials and model environment variables described above in the deployment environment.

## Arguments

- `--framework dify`: migrate as a Dify workflow.
- `create`: create a remote migration job.
- `status`: query the job and download results.
- `list`: view local `.agentkit/migrate/jobs` records.
- `--model-api-key-env`: defaults to `MODEL_AGENT_API_KEY` when omitted.

## License

Apache 2.0 License.
