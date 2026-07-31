# Any Generic Migration to AgentKit Runtime Sample

## Overview

AgentKit Runtime natively supports mainstream agent frameworks, including LangChain, LangGraph, Strands, Google ADK, and projects built on Bedrock AgentCore Runtime. For Python agent projects that are not explicitly adapted yet, have flexible structures, or need automated migration analysis, you can use `--framework any` for generic migration.

This directory demonstrates the `--framework any` migration flow: submit an existing Python agent project to a remote Codex sandbox for analysis, then generate a VeADK / AgentKit Runtime project that can run on AgentKit Runtime.

The source project in this sample is a Strands travel-planning agent. It uses `--framework any` to show how generic migration can infer the project structure without requiring the user to declare the exact framework manually.

## Source Input

The input directory is `any_input/`, which contains a travel-planning agent:

- Entry code: `any_input/agent.py`
- Framework: Strands `Agent`
- Tools: city note search, budget estimation, and transportation recommendation
- Migration goal: let the Codex sandbox understand the project structure automatically and generate a VeADK / AgentKit Runtime output project

## Install Dependencies

Install dependencies from this sample directory:

```bash
pip install -r requirements.txt
```

You can also use `uv`:

```bash
uv pip install -r requirements.txt
```

## Environment Variables

Prepare AgentKit account credentials and model configuration first. Do not write real secrets into the README, `.env`, or the code repository.

Keep only variable names in `.env.example`:

```text
MODEL_AGENT_NAME=
MODEL_AGENT_PROVIDER=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=
```

Volcengine China:

```bash
# AgentKit
export VOLCENGINE_ACCESS_KEY=""
export VOLCENGINE_SECRET_KEY=""

# 方舟模型
export MODEL_AGENT_NAME=""
export MODEL_AGENT_PROVIDER="openai"
export MODEL_AGENT_API_BASE="https://ark.cn-beijing.volces.com/api/v3/responses"
export MODEL_AGENT_API_KEY=""
```

BytePlus:

```bash
# BytePlus 模型
export MODEL_AGENT_NAME=""
export MODEL_AGENT_PROVIDER="openai"
export MODEL_AGENT_API_BASE="https://ark.ap-southeast.bytepluses.com/api/v3/"
export MODEL_AGENT_API_KEY=""

# BytePlus AgentKit
export BYTEPLUS_ACCESS_KEY=""
export BYTEPLUS_SECRET_KEY=""
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_REGION=ap-southeast-1
```

If model environment variables are absent, the source agent uses a local demo model so you can inspect the local behavior first.

## Run The Source Project Locally

Enter the source project directory that contains `agent.py`, then run:

```bash
python agent.py
```

## Create A Migration Job

`create` starts a real remote migration job. Run it only after confirming the environment variables and input directory. Make sure the `agentkit` CLI command is available before running it.

```bash
source .venv/bin/activate

# 如果已经有模型 key，可以映射给 migrate 远端 Codex 模型 key。
# 或者不设置这一行，在 create 命令后追加对应的 --codex-api-key-env 参数。
export AGENTKIT_MIGRATE_MODEL_API_KEY=""

cd <project_dir>/any/any_input
agentkit migrate . --framework any create --name any-test --output ../any_output
```

This command submits `any_input/` as the source project and writes the final artifacts to the directory specified by `--output`.

## Query And Download Results

Query the job status and download the final artifacts:

```bash
agentkit migrate . --framework any status --job-id <job_id>
```

You can also use the positional argument form:

```bash
agentkit migrate . --framework any status <job_id>
```

View local migration job records:

```bash
agentkit migrate . --framework any list
```

## Output

After migration completes, the directory specified by `--output` contains a VeADK / AgentKit Runtime project that can directly run `agentkit deploy`, plus `.agentkit/` configuration. The exact files depend on the actual migration output.

## Deploy

Enter the migration output directory, review `.agentkit/agentkit.yaml`, then run:

```bash
agentkit deploy
```

Continue using the AgentKit account credentials and model environment variables described above in the deployment environment.

## Example Inputs

- I want to take my parents to Beijing for 3 days with a total budget of 3000 RMB. We like history and culture, hutongs, and old Beijing food. Please keep the itinerary relaxed and plan attractions, food, and transportation for each day.
- I want to visit Xi'an for 2 days with a budget of 1800 RMB. I like historical sites and local snacks. Please arrange a relaxed route.

## Arguments

- `--framework any`: use generic agentic migration.
- `create`: create a remote migration job.
- `status`: query the job and download results.
- `list`: view local `.agentkit/migrate/jobs` records.
- `--model-api-key-env`: defaults to `MODEL_AGENT_API_KEY` when omitted.

## License

Apache 2.0 License.
