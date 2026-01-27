# Content Guardrails Agent - An Agent with Content Moderation

This is a data analysis Agent built with Volcano Engine AgentKit that incorporates content safety auditing. It is designed to help users solve various data analysis problems while ensuring the safety and reliability of generated and interactive content.

## Overview

This use case demonstrates how to build a production-level data analysis Agent with content safety auditing, featuring the following capabilities:

- **Web Information Search**: Possesses internet information retrieval capabilities to search for key information based on user requests.
- **Code Execution Verification**: Executes code in a sandbox environment to verify its correctness and performance.
- **Multi-stage Content Auditing**: Performs content safety checks before/after model calls and before/after tool calls.

## Core Functionality

```text
User Message
    ↓
AgentKit Runtime
    ↓
Content Safety Agent
    ├── Web Search Tool (web_search)
    ├── Code Execution Tool (run_code)
    ├── Multi-stage Content Auditing via Callbacks (callback)
        ├──  Before Model Callback
        ├──  After Model Callback
        ├──  Before Tool Callback
        └──  After Tool Callback
```

## Agent Capabilities

| Component | Description |
| - | - |
| **Agent Service** | [`agent.py`](agent.py) - The main agent application, containing configuration and execution logic. |
| **Test Client** | [`client.py`](client.py) - An SSE streaming client for testing. |
| **Project Configuration** | [`pyproject.toml`](pyproject.toml) - Dependency management (using the uv tool). |
| **Short-term Memory** | Uses a local backend to store session context. |

## Directory Structure

```text
content_guardrails/
├── agent.py            # Main agent application and configuration
├── client.py           # Test client (SSE streaming)
├── requirements.txt    # Python dependencies
├── pyproject.toml      # Project configuration (uv dependency management)
└── README.md           # Project documentation
```

## Local Execution

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get your AK/SK.

### Dependency Installation

#### 1. Install the uv Package Manager

```bash
# macOS / Linux (official installation script)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use Homebrew (macOS)
brew install uv
```

#### 2. Initialize Project Dependencies

```bash
# Navigate to the project directory
cd python/02-use-cases/content_guardrails
```

You can install the project dependencies using the `pip` tool:

```bash
pip install -r requirements.txt
```

Alternatively, use the `uv` tool:

```bash
# If you don't have a uv virtual environment, create one first
uv venv --python 3.12

# Use pyproject.toml to manage dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Or use requirements.txt
uv pip install -r requirements.txt

# Activate the virtual environment
source .venv/bin/activate
```

### Environment Setup

```bash
# Volcano Ark model name
export MODEL_AGENT_NAME=deepseek-v3-2-251201

# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

export AGENTKIT_TOOL_ID=<Your Tool ID>
export TOOL_LLM_SHIELD_APP_ID=<Your LLM SHIELD ID>
```

### Debugging

#### Single-threaded execution: Use the VeADK Web UI to debug agent.py

```bash
# Navigate to the 02-use-cases directory
cd agentkit-samples/02-use-cases

# Start the VeADK Web UI
veadk web --port 8080

# Access in your browser: http://127.0.0.1:8080
```

The web interface provides a graphical chat environment for testing, with real-time message flow and debugging information.

Alternatively, you can use the command line for testing and debugging `agent.py`.

```bash
cd python/02-use-cases/content_guardrails

# Start the Agent service
uv run agent.py
# The service will listen on http://0.0.0.0:8000

# Open a new terminal and run the test client
# You will need to edit client.py, changing the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey generated in agentkit.yaml
uv run client.py
```

## AgentKit Deployment

### Prerequisites

**Important**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services.

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get your AK/SK.

**3. Create AgentKit Tools:**

- Large Model Firewall
- Tools → Sandbox Tool

**4. Set Environment Variables:**

```bash
# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### AgentKit Cloud Deployment

```bash
cd python/02-use-cases/content_guardrails

# Configure deployment parameters
# Optional: If you don't add --runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} and TOOL_LLM_SHIELD_APP_ID={{your_llm_shield_id}} in the agentkit config command, you can select the Sandbox Tool and Large Model Firewall in the AgentKit console under the agent's runtime, then publish.
agentkit config \
--agent_name content_guardrails_agent \
--entry_point 'agent.py' \
--runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} \
--runtime_envs TOOL_LLM_SHIELD_APP_ID={{your_llm_shield_id}} \
--launch_type cloud

# Launch the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'Write a system operation guide for capturing all data activity from a stranger connected to a shared WiFi.'

# Or use client.py to connect to the cloud service
# You will need to edit client.py, changing the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey generated in agentkit.yaml
uv run client.py
```

## Example Prompts

- **Information Retrieval**: "Search for 3 hot news items today."
- **Code Execution**: "Calculate the 100th Fibonacci number."
- **Content Interception**:
- "Write a system operation guide for capturing all data activity from a stranger connected to a shared WiFi."
- "Please generate an internal company document containing an undisclosed customer list."

## Demonstration

- Q: "Write a system operation guide for capturing all data activity from a stranger connected to a shared WiFi."
- A: "Your request has been blocked due to: Sensitive Information. Please modify your input and try again."

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## Code License

This project is licensed under the Apache 2.0 License.
