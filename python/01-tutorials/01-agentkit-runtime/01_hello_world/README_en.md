# Hello World - The Simplest Chat Agent

This is an entry-level conversational agent built based on Volcano Engine VeADK and AgentKit, demonstrating how to create a basic AI Agent with short-term memory.

## Overview

This example is the "Hello World" of AgentKit, showcasing the most basic Agent building process.

## Core Features

- Create a simple conversational Agent
- Use local short-term memory to maintain conversation context
- Implement information memory in multi-turn conversations
- Support local debugging and cloud deployment

## Agent Capability

```text
User Message
    ↓
AgentKit Runtime
    ↓
Hello World Agent
    ├── VeADK Agent (Conversation Engine)
    ├── ShortTermMemory (Session Memory)
    └── Volcano Ark Model (LLM)
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world.py) - Main application, defines the Agent and memory components |
| **Test Client** | [client.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world/client.py) - SSE streaming call client |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world/pyproject.toml) - Dependency management (uv tool) |
| **AgentKit Configuration** | agentkit.yaml - Cloud deployment configuration file |
| **Short-Term Memory** | Use local backend to store session context |

### Code Features

**Agent Definition** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world/agent.py#L11-L18)):

```python
agent = Agent()
short_term_memory = ShortTermMemory(backend="local")

runner = Runner(
    agent=agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id
)
```

**Multi-turn Conversation Test** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world/agent.py#L21-L26)):

```python
async def main():
    response1 = await runner.run(messages="My name is VeADK", session_id=session_id)
    response2 = await runner.run(messages="Do you remember my name?", session_id=session_id)
```

## Directory Structure Description

```bash
01_hello_world/
├── agent.py           # Agent application entry point
├── client.py          # Test client (SSE streaming call)
├── requirements.txt   # Python dependency list (required for agentkit deployment)
├── pyproject.toml     # Project configuration (uv dependency management)
├── agentkit.yaml      # AgentKit deployment configuration (auto-generated after running agentkit config)
├── Dockerfile         # Docker image build file (auto-generated after running agentkit config)
└── README.md          # Project documentation
```

## Local Execution

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get AK/SK

### Dependency Installation

#### 1. Install uv Package Manager

```bash
# macOS / Linux (official installation script)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use Homebrew (macOS)
brew install uv
```

#### 2. Initialize Project Dependencies

```bash
# Enter the project directory
cd python/01-tutorials/01-agentkit-runtime/01_hello_world
```

Use the `uv` tool to install the project dependencies:

```bash
# If you don't have a `uv` virtual environment, you can create one first
uv venv --python 3.12

# Use `pyproject.toml` to manage dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Activate the virtual environment
source .venv/bin/activate
```

### Environment Preparation

```bash
# Volcano Ark Model Name
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# Volcano Engine Access Credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Debugging Methods

#### Method 1: Use VeADK Web Debugging Interface

```bash
# Go to the parent directory
cd python/01-tutorials/01-agentkit-runtime

# Start the VeADK Web interface
veadk web --port 8080

# Access in your browser: http://127.0.0.1:8080
```

The web interface provides a graphical conversation testing environment, supporting real-time viewing of message flows and debugging information.

#### Method 2: Command Line Testing

```bash
cd python/01-tutorials/01-agentkit-runtime/01_hello_world

# Start the Agent service
uv run agent.py
# The service will listen on http://0.0.0.0:8000

# Open a new terminal and run the test client
# You need to edit client.py and change the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
uv run client.py
```

**Execution Effect**:

```bash
[create session] Response from server: {"session_id": "agentkit_session"}
[run agent] Event from server:
data: {"event":"on_agent_start",...}
data: {"event":"on_llm_chunk","data":{"content":"Hello VeADK! Nice to meet you."}}
data: {"event":"on_llm_chunk","data":{"content":"Of course I remember, your name is VeADK."}}
```

## AgentKit Deployment

### Prerequisites

**Important Note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the case can be executed normally.

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get AK/SK

### AgentKit Cloud Deployment

```bash
cd python/01-tutorials/01-agentkit-runtime/01_hello_world

# Configure deployment parameters
agentkit config

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'who r u'

# Or use client.py to connect to the cloud service
# You need to edit client.py and change the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
uv run client.py
```

## Example Prompts

### Basic Conversation Test

**Test Short-Term Memory**:

```text
User: My name is VeADK
Agent: Hello VeADK! Nice to meet you.

User: Do you remember my name?
Agent: Of course I remember, your name is VeADK.
```

### More Test Scenarios

**Test Information Memory**:

```text
User: I am 25 years old and I like programming
Agent: Got it! You are 25 years old and you like programming, that's a great hobby.

User: How old am I? What are my hobbies?
Agent: You are 25 years old and you like programming.
```

**Test Context Association**:

```text
User: I live in Beijing and work at an internet company
Agent: Understood, you work in Beijing at an internet company.

User: Do you know my basic information?
Agent: Yes, your name is VeADK, you are 25 years old, you like programming, and you work at an internet company in Beijing.
```

## Effect Display

## Technical Points

### Short-Term Memory

- **Storage Method**: Local memory (`backend="local"`)
- **Scope**: All conversations within a single session_id
- **Lifecycle**: Cleared after process restart
- **Applicable Scenarios**: Development and debugging, single-machine deployment

### Multi-turn Conversation

- Associate the same conversation through `session_id`
- Automatically load historical messages with each call
- The Agent understands the user's intent based on the context

### AgentKit Integration

```python
from agentkit.apps import AgentkitAgentServerApp

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)
```

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## Code License

This project follows the Apache 2.0 License
