# mem0 memory - Long and Short Term Memory Agent

This is a memory management example based on Volcano Engine VeADK and mem0, demonstrating how to implement the short-term and long-term memory functions of an agent.

## Overview

This example demonstrates two memory mechanisms of VeADK to help understand the memory system of an agent.

## Core Functions

- Short-term memory: Only valid within the same session.
- Long-term memory: Based on mem0, can be persistently stored across sessions.
- Memory conversion: Convert short-term memory to long-term memory.
- Memory retrieval: Query historical information through the LoadMemory tool.

## Agent Capabilities

```text
User Interaction
    ↓
Agent + Runner
    ├── ShortTermMemory
    │   └── Local memory storage
    │   └── Session-level isolation
    │
    └── LongTermMemory
        └── mem0 persistence
        └── Shared across sessions
        └── LoadMemory tool for retrieval
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/mem0_memory/agent.py) - Main application, integrating short-term and long-term memory |
| **Short-term Memory** | ShortTermMemory - Session-level temporary storage |
| **Long-term Memory** | LongTermMemory - mem0 persistent storage |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/mem0_memory/pyproject.toml) - Dependency management (uv tool) |

### Code Features

```python
# Short-term memory: only valid in the same session
agent1 = Agent(
    name="test_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v3-2-251201"),
    instruction="You are a helpful assistant.",
)

runner1 = Runner(
    agent=agent1,
    short_term_memory=ShortTermMemory(),
    app_name=app_name,
    user_id=user_id,
)
```

```python
# Initialize long-term memory (mem0 backend)
long_term_memory = LongTermMemory(backend="mem0", app_name=app_name, user_id=user_id)
agent1.long_term_memory = long_term_memory

# Convert short-term to long-term memory
await runner1.save_session_to_long_term_memory(session_id=history_session_id)

# Long-term memory: valid across sessions
agent2 = Agent(
    name="test_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v3-2-251201"),
    instruction="Use LoadMemory tool to search previous info.",
    long_term_memory=long_term_memory,
)
```

## Directory Structure

```text
viking_memory/
├── agent.py           # Agent application entry point
├── requirements.txt   # Python dependency list (required for agentkit deployment)
├── pyproject.toml     # Project configuration (uv dependency management)
└── README.md          # Project documentation
```

## Local Execution

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Activate mem0 Memory Store:**

- Visit [mem0 Console](https://console.volcengine.com/mem0/region:mem0+cn-beijing/list?projectName=default)
- Create a memory store instance

**3. Obtain Volcano Engine Access Credentials:**

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
cd python/01-tutorials/05-agentkit-memory/mem0_memory
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

### Environment Setup

```bash
# Volcano Ark model name
export MODEL_AGENT_NAME=deepseek-v3-2-251201

# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Debugging Methods

#### Method 1: Use VeADK Web Debugging Interface

```bash
# Go to the parent directory
cd python/01-tutorials/05-agentkit-memory

# Start the VeADK Web interface
veadk web

# Access in your browser: http://127.0.0.1:8000
```

The web interface provides a graphical dialogue testing environment, supporting real-time viewing of memory status and debugging information.

#### Method 2: Command-line Testing (Recommended for learning)

```bash
# Start the Agent service directly
uv run agent.py
# The service will listen on http://0.0.0.0:8000
uv run client.py # Test memory effect
```

## AgentKit Deployment

### Prerequisites

**Important Note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the case can be executed normally.

**1. Activate Volcano Ark Model Service:**

- Visit [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Activate mem0 Memory Store:**

- Visit [mem0 Console](https://console.volcengine.com/mem0/region:mem0+cn-beijing/list?projectName=default)
- Create a memory store instance

**3. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get AK/SK

### AgentKit Cloud Deployment

```bash
cd python/01-tutorials/05-agentkit-memory/mem0_memory

# Configure deployment parameters
agentkit config \
--agent_name mem0_agent \
--entry_point 'agent.py' \
--runtime_envs MEM0_APP_NAME=mem0_agent_app \
--launch_type cloud

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'What is my hobby?'
```

## Example Prompts

### Short-term Memory Test

**Save information to short-term memory:**

```text
User: My hobby is 0xabcd
Agent: Your hobby is 0xabcd.
(Information stored in session: history_session)
```

**Query in the same session (success):**

```text
User: What is my hobby?
Agent: Your hobby is 0xabcd.
(Using the same session_id: history_session)
```

### Long-term Memory Test

**Convert to long-term memory:**

```python
# Save short-term memory to long-term memory, here we have already added it to long-term memory by default
# This is just a demonstration of memory saving. You can implement a tool to let the agent save session content to long-term memory according to actual needs.
async def after_agent_execution(callback_context: CallbackContext):
    session = callback_context._invocation_context.session
    await long_term_memory.add_session_to_memory(session)
```

**Query across sessions (success):**

```text
User: What is my hobby?
Agent: According to memory, your hobby is 0xabcd.
(Using a new session_id: new_session, long-term memory takes effect)
(The agent automatically calls the LoadMemory tool to retrieve historical information)
```

## Effect Display

## Technical Points

### Short-term Memory (ShortTermMemory)

- **Storage method**: Local memory
- **Scope**: All dialogues within a single session_id
- **Lifecycle**: Cleared after process restart
- **Applicable scenarios**: Context maintenance for a single session
- **Features**: Fast, lightweight, but not persistent

### Long-term Memory (LongTermMemory)

- **Storage method**: mem0 memory store
- **Scope**: Across sessions, based on user_id and app_name
- **Lifecycle**: Persistent storage, not affected by processes
- **Applicable scenarios**: User preferences, historical records, knowledge accumulation
- **Features**: Persistent, searchable, supports semantic search

### Memory Conversion

```python
# Save short-term memory to long-term memory
await runner.save_session_to_long_term_memory(session_id=session_id)
```

### LoadMemory Tool

When an Agent is configured with long-term memory, it automatically gets the `LoadMemory` tool:

```python
agent = Agent(
    instruction="Use LoadMemory tool to search previous info.",
    long_term_memory=long_term_memory,
)
```

The Agent can automatically call the `LoadMemory` tool to retrieve historical memory without manual processing.

### AgentKit Integration

```python
from agentkit.apps import AgentkitAgentServerApp

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)
```

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [mem0 Documentation](https://www.volcengine.com/docs/86722/1852874?lang=en)

## Code License

This project follows the Apache 2.0 License
