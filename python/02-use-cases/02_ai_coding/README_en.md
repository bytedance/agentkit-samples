# AI Coding Agent

This is an intelligent programming assistant system built with Volcano Engine AgentKit, designed to help users solve various programming problems. The system integrates a code execution sandbox and TOS object storage service to provide a professional and efficient programming assistance experience.

## Overview

This use case demonstrates how to build a production-level AI programming assistant system with the following capabilities:

- **Intelligent Programming Dialogue**: An AI-based intelligent programming assistant that understands user programming needs and provides accurate code solutions.
- **Code Execution and Verification**: Executes code in a sandbox environment to verify its correctness and performance.
- **Frontend Code Hosting**: Automatically uploads frontend code (HTML/CSS/JS) to TOS object storage and generates an accessible preview link.
- **Multi-language Support**: Supports multiple programming languages such as Python, Java, JavaScript, and Go.
- **Long-Term Memory**: Supports session memory and user history storage.
- **Observability**: Integrated with OpenTelemetry for tracing and APMPlus for monitoring.

## Core Functionality

![AI Coding Agent with AgentKit Runtime](img/archtecture_ai_coding.jpg)

```text
User Request
    ↓
AgentKit Runtime
    ↓
AI Programming Assistant
    ├── Code Execution Tool (run_code)
    ├── TOS Upload Tool (upload_frontend_code_to_tos)
    └── URL Generation Tool (get_url_of_frontend_code_in_tos)
```

## Agent Capabilities

| Component | Description |
| - | - |
| **Agent Service** | [`agent.py`](agent.py) - The main agent application, containing configuration and runtime logic |
| **Tool Module** | [`tools.py`](tools.py) - TOS upload, URL generation, and utility functions |
| **Sandbox Execution** | A secure code execution environment supporting Python, Java, JavaScript, and Go |
| **TOS Integration** | An object storage service for hosting frontend code and providing public access |

### Multi-language Support

Supports mainstream programming languages like Python, Java, JavaScript, and Go, with automatic syntax validation.

### Sandbox Execution

Runs code in an isolated environment to ensure security and prevent system interference.

### Automated Deployment

Frontend code is automatically uploaded to TOS, and a preview URL is generated for immediate testing.

### Observability

Built-in OpenTelemetry tracing and APMPlus monitoring to support production environment debugging and performance analysis.

## Directory Structure

```text
02_ai_coding/
├── agent.py              # Main agent application and configuration
├── tools.py              # Tool functions (TOS upload, URL generation)
├── requirements.txt      # Python dependencies
└── README.md            # Project documentation
```

## Local Execution

### Prerequisites

#### Volcano Engine Access Credentials

1. Log in to the [Volcano Engine Console](https://console.volcengine.com)
2. Go to "Access Control" → "Users" -> Create a new user or search for an existing one -> Click the username to go to "User Details" -> Go to "Keys" -> Create a new key or copy an existing AK/SK.
   - As shown below:
   ![Volcengine AK/SK Management](../../assets/images/volcengine_aksk.jpg)
3. Configure access permissions for services required by AgentKit:
   - On the "User Details" page -> Go to "Permissions" -> Click "Add Permission" and grant the following policies to the user:
   - `AgentKitFullAccess` (Full access to AgentKit)
   - `APMPlusServerFullAccess` (Full access to APMPlus)
4. Obtain a Volcano Ark model Agent API Key:
   - Log in to the [Volcano Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)
   - Go to "API Key Management" -> Create or copy an existing API Key. The `MODEL_AGENT_API_KEY` environment variable will need to be set to this value.
   - As shown below:
   ![Ark API Key Management](../../assets/images/ark_api_key_management.jpg)
5. Activate pre-built model inference endpoints:
   - Log in to the [Volcano Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)
   - Go to "Activation Management" -> "Language Models" -> Find the desired model -> Click "Activate Service".
   - Confirm activation and wait for the service to become effective (usually 1-2 minutes).
   - Activate the following models used in this case:
        - `deepseek-v3-1-terminus`
        - `doubao-seed-code-preview-251028`
   - As shown below:
   ![Ark Model Service Management](../../assets/images/ark_model_service_management.jpg)

#### AgentKit Tool ID

1. Log in to the Volcano Engine AgentKit console.
2. Go to "Tools" → "Create Sandbox Tool".
3. Create the tool:
   - Tool Name: `ai-coding-agent`
   - Description: AI Programming Assistant Tool
4. Copy the generated Tool ID for configuration (the `AGENTKIT_TOOL_ID` environment variable will need to be set to this value), as shown below:
   ![AgentKit Sandbox Tool](../../assets/images/agentkit_sandbox_tool.jpg)

### Install Dependencies

*It is recommended to use the `uv` tool to build the project.*

```bash
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

cd python/02-use-cases/02_ai_coding

# create virtual environment
uv venv --python 3.12

# activate virtual environment
source .venv/bin/activate

# install necessary dependencies
uv pip install -r requirements.txt
```

### Configure Environment Variables

Set the following environment variables:

```bash
export VOLCENGINE_ACCESS_KEY={your_ak}
export VOLCENGINE_SECRET_KEY={your_sk}
export DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}
export AGENTKIT_TOOL_ID={{your_tool_id}}
export MODEL_AGENT_API_KEY={{your_model_agent_api_key}} # Required for local debugging, obtained from Volcano Ark
```

**Environment Variable Explanations:**

- `VOLCENGINE_ACCESS_KEY`: The Access Key for your Volcano Engine credentials.
- `VOLCENGINE_SECRET_KEY`: The Secret Key for your Volcano Engine credentials.
- `DATABASE_TOS_BUCKET`: The name of the TOS bucket for storing generated frontend code.
  - Format: `DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}`
  - Example: `DATABASE_TOS_BUCKET=agentkit-platform-12345678901234567890`
  - `{{your_account_id}}` needs to be replaced with your Volcano Engine account ID.
- `AGENTKIT_TOOL_ID`: The Tool ID obtained from the AgentKit console.
- `MODEL_AGENT_API_KEY`: The Model Agent API Key obtained from Volcano Ark.

## Testing

Use `veadk web` for local debugging:

> `veadk web` is a FastAPI-based web service for debugging Agent applications. Running this command starts a web server that loads and runs your AgentKit agent code, providing a chat interface to interact with the agent. In the sidebar or specific panels of the interface, you can view the agent's operational details, including its thought process, tool calls, and model inputs/outputs.

```bash
# 1. Go to the parent directory
cd 02-use-cases

# 2. Optional: Create a .env file (skip if environment variables are already set)
touch .env
echo "VOLCENGINE_ACCESS_KEY=AK" >> .env
echo "VOLCENGINE_SECRET_KEY=SK" >> .env
echo "DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}" >> .env
echo "AGENTKIT_TOOL_ID={{your_tool_id}}" >> .env
echo "MODEL_AGENT_API_KEY={{your_model_agent_api_key}}" >> .env

# 3. Start the Web UI
veadk web
```

The service runs on port 8000 by default. Access `http://127.0.0.1:8000`, select the `02_ai_coding` agent, and start testing.

### Example Prompts

- **Frontend Code Generation**: "Please write a debounce function for me in JavaScript."
- **Python Code Generation**: "Write a function to generate the Fibonacci sequence."
- **Algorithm Implementation**: "Create a binary search implementation in Python."

## AgentKit Deployment

1. Deploy to Volcano Engine AgentKit Runtime:

```bash
# 1. Go to the project directory
cd python/02-use-cases/02_ai_coding

# 2. Configure agentkit
agentkit config \
--agent_name ai_coding \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}} \
--runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} \
--launch_type cloud

# 3. Deploy to runtime
agentkit launch
```

1. Invoke the agent

```bash
agentkit invoke '{"prompt": "Create a binary search implementation in Python."}'
```

## FAQ

**Error: `DATABASE_TOS_BUCKET not set`**

- The TOS bucket name for code uploads must be set via an environment variable.

**Code Execution Timeout:**

- Check the sandbox service status and network connection.
- Verify the code complexity and execution time requirements.

**TOS Upload Failed:**

- Confirm that the Access Key/Secret Key has TOS write permissions.
- Verify the bucket name and region configuration.

## Demonstration

AI Coding demonstration.

## FAQ

None.

## 🔗 Related Resources

- [AgentKit Official Documentation](https://www.volcengine.com/docs/86681/1844878?lang=en)
- [TOS Object Storage](https://www.volcengine.com/product/TOS)
- [AgentKit Application Square](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/application)
- [AgentKit Console](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/overview?projectName=default)

## Code License

This project is licensed under the Apache 2.0 License.
