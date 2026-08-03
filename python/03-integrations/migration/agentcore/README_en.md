# Bedrock AgentCore Migration to AgentKit Runtime Sample

## Overview

This sample shows how to connect an existing Bedrock AgentCore Runtime project to AgentKit Runtime.

This sample uses `agent.py` to simulate an existing Bedrock AgentCore Runtime customer-support project and shows how to migrate it to AgentKit Runtime.

This demo guides you through adapting the Bedrock AgentCore Runtime project, generating artifacts that can be deployed to AgentKit Runtime, and completing the deployment.

## Key Features

- Shows how an existing Bedrock AgentCore Runtime project connects to AgentKit Runtime.
- Preserves the `@app.entrypoint` business entry and continues to run a Strands Agent inside it.
- Uses Strands `Agent` to organize the model, prompt, and tools.
- Uses `@tool` to declare local product lookup and return policy tools.
- Preserves the native AgentCore business code and generates Runtime entry files and configuration through `agentkit migrate`.

## Agent Capabilities

This sample includes the following local tools:

- `get_product_info`: looks up built-in product data by product ID.
- `get_return_policy`: looks up built-in return policies by product category.

After migration, the call flow is:

```text
User question
    ↓
AgentKit Runtime
    ↓
agentkit_app.py
    ↓
BedrockAgentCoreAgentkitBridge
    ↓
agent.py:app
    ↓
@app.entrypoint invoke
    ↓
Strands Agent
    ├── get_product_info
    └── get_return_policy
```

## Directory Structure

```bash
agentcore/
├── .env.example       # Model configuration environment variable example
├── README.md          # Chinese README
├── README_en.md       # English README
├── agent.py           # Native Bedrock AgentCore app, Strands Agent, and local tools
└── requirements.txt   # Python dependencies
```

## Local Run

### Check AgentKit CLI Version

First make sure the TypeScript version of AgentKit CLI is installed and the version is not lower than `0.50.4`:

```bash
agentkit -v
```

If it is not installed, or the version is lower than `0.50.4`, install the TypeScript version of AgentKit CLI with:

```bash
curl https://agentkit-cli.tos-cn-beijing.volces.com/install.sh | sh
```

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

This sample uses Strands `OpenAIModel` to create the model, so `MODEL_AGENT_PROVIDER` is not required. Make sure your model endpoint supports the OpenAI format.

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

Before migration, first make sure the original AgentCore project is healthy and runnable:

```bash
python agent.py
```

After the service starts, you can call it with the native AgentCore `/invocations` protocol:

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt":"How much is PROD-002 smart watch? Can I return it if it does not fit?"}'
```

This command calls the AgentCore entrypoint behind `agent.py:app`, sends a fixed customer-support question to the Strands Agent, and uses the configured OpenAI-compatible model to complete one real conversation.

### Run The Migration Command

After confirming that the original project is executable, run the migration command to generate Runtime entry files and configuration:

```bash
agentkit migrate . \
  --framework agentcore \
  --entry agent.py:app \
  --name migration-agentcore-strands \
  --verify
```

Arguments:

- `--framework agentcore`: migrate as a Bedrock AgentCore Runtime entrypoint.
- `--entry agent.py:app`: specify the native `BedrockAgentCoreApp` entry.
- `--verify`: run basic checks after generation.

Note that this is not `--framework strands`. Although the business agent is written with Strands, the project entry being migrated is `BedrockAgentCoreApp`.

After the command succeeds, it generates entry files and configuration that can be deployed to AgentKit Runtime.
The migration process does not rewrite the original AgentCore `agent.py`.

## AgentKit Deployment

If you want to deploy the generated artifacts to AgentKit Runtime, run:

```bash
agentkit deploy
```

After deployment, you can find the deployed project in AgentKit Runtime on the AgentKit platform.

## Example Prompts

- How much is PROD-002 smart watch? Can I return it if it does not fit?
- I want to buy headphones. Please look up the product information and return policy.

## Example Output

After running an example prompt, the Agent calls local product data and return policy tools through Strands, then outputs product price, category, warranty, and return rules.

```text
The Smart Watch costs $249.99, belongs to electronics, and has a 24 months warranty.
The electronics return policy has a 30-day return window. Returns for non-quality issues require the original packaging.
```

## FAQ

- Does the migration command rewrite the original `agent.py`?

  No. The migration command adds Runtime entry files, while the original AgentCore business entry remains unchanged.

## License

This project is licensed under the Apache 2.0 License.
