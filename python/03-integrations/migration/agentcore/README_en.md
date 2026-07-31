# Bedrock AgentCore Project Adaptation to AgentKit Runtime Sample

## Overview

This sample shows how to adapt an existing Bedrock AgentCore Runtime project to AgentKit Runtime.

The sample project represents a user-owned AgentCore Runtime customer-support agent. Its native entry point is `agent.py:app`, implemented as `BedrockAgentCoreApp`. The `@app.entrypoint` handler runs a Strands Agent with local tools for product lookup and return-policy lookup.

You do not need to rewrite the original AgentCore entry point during adaptation. `agentkit migrate` generates `agentkit_app.py` and `.agentkit/` configuration, and the generated Runtime app calls the original `agent.py:app` through `BedrockAgentCoreAgentkitBridge`.

## Key Features

- Shows how a Bedrock AgentCore Runtime `BedrockAgentCoreApp` entry point is called by AgentKit Runtime.
- Preserves the `@app.entrypoint` business entry while still running a Strands Agent inside it.
- Uses `@tool` to declare local product lookup and return-policy tools.
- Uses Strands `OpenAIModel` for OpenAI-compatible model calls, compatible with `MODEL_AGENT_NAME`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY`.
- Keeps local tools as minimal mock data so the sample focuses on the migration structure.

## Agent Capabilities

This sample includes the following local tools:

- `get_product_info`: looks up built-in product data by product ID.
- `get_return_policy`: looks up built-in return policy by product category.

After adaptation, the call flow is:

```text
User question
    |
AgentKit Runtime
    |
agentkit_app.py
    |
BedrockAgentCoreAgentkitBridge
    |
agent.py:app  # BedrockAgentCoreApp
    |
@app.entrypoint invoke
    |
Strands Agent
    |-- OpenAIModel
    |-- get_product_info
    `-- get_return_policy
```

## Directory Layout

```bash
agentcore/
├── .env.example       # Model config variable names
├── README.md          # Chinese documentation
├── README_en.md       # English documentation
├── agent.py           # Native Bedrock AgentCore app, Strands Agent, and tools
└── requirements.txt   # Dependencies split into native AgentCore agent and AgentKit runtime sections
```

Running `agentkit migrate` in this directory generates `agentkit_app.py` and `.agentkit/`. Generated files do not need to be committed as part of the sample source.

## Local Run

### Install Dependencies

Use Python 3.10 or later. From this sample directory, run:

```bash
pip install -r requirements.txt
```

You can also use `uv`:

```bash
uv pip install -r requirements.txt
```

### Configure Environment

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

When `MODEL_AGENT_NAME` and `MODEL_AGENT_API_KEY` are configured, the code creates a model with Strands `OpenAIModel`. The provider is determined by that class, so `MODEL_AGENT_PROVIDER` is not required. `MODEL_AGENT_API_BASE` may point to the Ark Responses endpoint; the sample normalizes it to the OpenAI-compatible API root before passing it to `OpenAIModel`.

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

Account credentials are not written to `.env.example` or `.env`, and are not read by the native AgentCore business agent.

Set `MODEL_AGENT_NAME` and `MODEL_AGENT_API_KEY` before running `python agent.py` or migration with `--verify`. If they are missing, the sample raises a clear error instead of mixing a fake local model with the real Strands call path.

### Debug Locally

Start the native Bedrock AgentCore Runtime local server:

```bash
python agent.py
```

Then call the native AgentCore `/invocations` protocol:

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt":"How much is PROD-002, and can I return it if it does not fit?"}'
```

You can also debug the migrated Runtime app. First run:

```bash
agentkit migrate . \
  --framework agentcore \
  --entry agent.py:app \
  --name migration-agentcore-strands \
  --verify \
  --force
```

Arguments:

- `--framework agentcore`: migrate as a Bedrock AgentCore Runtime entrypoint.
- `--entry agent.py:app`: specify the native `BedrockAgentCoreApp` entry.
- `--verify`: run basic checks after generation.
- `--force`: overwrite old generated files if they already exist.

This is intentionally not `--framework strands`. The business agent is implemented with Strands, but the project entry being migrated is `BedrockAgentCoreApp`.

`agentkit migrate` may warn that model replacement is not enabled for an AgentCore project. This sample does not construct `BedrockModel` or `AnthropicModel`; the model layer already uses Strands `OpenAIModel` and the `MODEL_AGENT_*` environment variables, so you do not need to pass `--model-id`.

## Deploy To AgentKit Runtime

After reviewing `.agentkit/agentkit.yaml`, run:

```bash
agentkit deploy
```

After deployment, the Runtime entry point is `agentkit_app.py`. The business logic is still handled by the original `agent.py:app`, the AgentCore entrypoint, the Strands Agent, and the original tools.

Deployment needs model env vars in the deployment environment. Export account credentials with the Volcengine or BytePlus block above:

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

## Example Prompts

- How much is PROD-002, and can I return it if it does not fit?
- I want to buy headphones. Please look up the product information and return policy.

## Expected Output

Running an example prompt makes the agent use local product data and return-policy tools, then return product price, category, warranty, and return rules.

```text
Smart Watch costs $249.99, belongs to electronics, and has a 24 months warranty.
The electronics return policy has a 30-day return window and requires original packaging for non-defective returns.
```

## FAQ

- Why does this sample not use BedrockModel?

  To stay consistent with the other migration demos in this project, the sample uses Strands `OpenAIModel` with OpenAI-compatible model credentials. It directly reuses `MODEL_AGENT_NAME`, `MODEL_AGENT_API_BASE`, and `MODEL_AGENT_API_KEY`.

- What if model env vars are not configured?

  `agent.py` raises a clear error. Configure `MODEL_AGENT_NAME` and `MODEL_AGENT_API_KEY`, or only run a migration dry-run that does not import and execute the source agent.

- Does the migration command rewrite `agent.py`?

  No. The migration command adds Runtime adaptation files, while the original AgentCore business entry remains unchanged.

## License

This project is licensed under the Apache 2.0 License.
