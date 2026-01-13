# viking memory - Long and Short-Term Memory Agent

This is a memory management example built with Volcano Engine's VeADK and VikingDB, demonstrating how to implement short-term and long-term memory functions for an intelligent agent.

## Overview

This example demonstrates the two memory mechanisms of VeADK to help you understand the memory system of an intelligent agent.

## Core Features

- Short-term Memory: Effective only within the same session.
- Long-term Memory: Based on VikingDB, allowing for persistent storage across sessions.
- Memory Conversion: Converting short-term memory to long-term memory.
- Memory Retrieval: Querying historical information using the `LoadMemory` tool.

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
        └── VikingDB for persistence
        └── Shared across sessions
        └── Retrieval via LoadMemory tool
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/agent.py) - The main application, integrating short-term and long-term memory. |
| **Test Script** | [local_test.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/local_test.py) - A complete demonstration of memory functions. |
| **Short-term Memory** | `ShortTermMemory` - Session-level temporary storage. |
| **Long-term Memory** | `LongTermMemory` - Persistent storage in VikingDB. |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/pyproject.toml) - Dependency management (with `uv`). |

### Code Highlights

**Short-term Memory Configuration** ([local_test.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/local_test.py#L26-L34)):

```python
# Short-term memory: effective only within the same session
agent1 = Agent(name="test_agent", instruction="You are a helpful assistant.")

runner1 = Runner(
    agent=agent1,
    short_term_memory=ShortTermMemory(),
    app_name=app_name,
    user_id=user_id,
)
```

**Long-term Memory Configuration** ([local_test.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/local_test.py#L56-L69)):

```python
# Initialize long-term memory (Viking backend)
long_term_memory = LongTermMemory(backend="viking", index=vikingmem_app_name)
agent1.long_term_memory = long_term_memory

# Convert short-term to long-term memory
await runner1.save_session_to_long_term_memory(session_id=history_session_id)

# Long-term memory: effective across sessions
agent2 = Agent(
    name="test_agent",
    instruction="Use LoadMemory tool to search previous info.",
    long_term_memory=long_term_memory,
)
```

## Directory Structure

```text
0_viking_memory/
├── agent.py           # Agent application entry point
├── local_test.py      # Complete memory function demonstration script
├── requirements.txt   # Python dependency list (required for agentkit deployment)
├── pyproject.toml     # Project configuration (for uv dependency management)
└── README.md          # Project documentation
```

## Local Execution

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Activate VikingDB Memory Base:**

- Visit the [VikingDB Console](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- Create a memory base instance

**3. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get your AK/SK

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
# Navigate to the project directory
cd python/01-tutorials/05-agentkit-memory/01_viking_memory
```

Use `uv` to install the project dependencies:

```bash
# If you don't have a `uv` virtual environment, create one first
uv venv --python 3.12

# Use `pyproject.toml` to manage dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Activate the virtual environment
source .venv/bin/activate
```

### Environment Setup

```bash
# Volcano Ark model name
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Debugging Methods

#### Method 1: Using the VeADK Web Debugging Interface

```bash
# Go to the parent directory
cd python/01-tutorials/05-agentkit-memory

# Start the VeADK Web interface
veadk web

# Access in your browser: http://127.0.0.1:8000
```

The web interface provides a graphical chat environment for testing and supports real-time viewing of memory status and debugging information.

#### Method 2: Command-Line Testing (Recommended for Learning)

```bash
# Start the Agent service directly
uv run agent.py
# The service will listen on http://0.0.0.0:8000
uv run client.py # Test memory effect

# Run the complete memory function demonstration
uv run local_test.py
```

## AgentKit Deployment

### Prerequisites

**Important Note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the case can execute normally.

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Activate VikingDB Memory Base:**

- Visit the [VikingDB Console](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- Create a memory base instance

**3. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get your AK/SK

### AgentKit Cloud Deployment

```bash
cd python/01-tutorials/05-agentkit-memory/01_viking_memory

# Configure deployment parameters
agentkit config \
--agent_name vikingmem_agent \
--entry_point 'agent.py' \
--runtime_envs VIKINGMEM_APP_NAME=vikingmem_agent_app \
--launch_type cloud

# Launch the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'What is my hobby?'
```

## Example Prompts

### Short-term Memory Test

**Save information to short-term memory**:

```text
User: My hobby is 0xabcd
Agent: Your hobby is 0xabcd.
(Information is stored in session: history_session)
```

**Query within the same session (successful)**:

```text
User: What is my hobby?
Agent: Your hobby is 0xabcd.
(Using the same session_id: history_session)
```

### Long-term Memory Test

**Convert to long-term memory**:

```python
# Save short-term memory to long-term memory. Here, we have already added it to long-term memory by default.
# This is just a demonstration of memory saving. You can implement a tool to let the agent save session content to long-term memory based on actual needs.
async def after_agent_execution(callback_context: CallbackContext):
    session = callback_context._invocation_context.session
    await long_term_memory.add_session_to_memory(session)
```

**Query across sessions (successful)**:

```text
User: What is my hobby?
Agent: According to my memory, your hobby is 0xabcd.
(Using a new session_id: new_session, long-term memory is effective)
(The Agent automatically calls the LoadMemory tool to retrieve historical information)
```

### Complete Demonstration Flow

Running `local_test.py` shows the complete memory function demonstration:

```text
Response 1: Your hobby is 0xabcd.

Response 2: Your hobby is 0xabcd.
(Short-term memory is effective)

Response 3: I do not have this information.
(New session, short-term memory is not effective)

Response 4: According to my memory, your hobby is 0xabcd.
(Long-term memory is effective, cross-session retrieval is successful)
```

## Effect Demonstration

## Technical Points

### Short-term Memory (ShortTermMemory)

- **Storage Method**: Local memory
- **Scope**: All conversations within a single `session_id`
- **Lifecycle**: Cleared after process restart
- **Applicable Scenarios**: Context maintenance for a single session
- **Features**: Fast, lightweight, but not persistent

### Long-term Memory (LongTermMemory)

- **Storage Method**: VikingDB vector database
- **Scope**: Across sessions, based on `user_id` and `app_name`
- **Lifecycle**: Persistent storage, not affected by process restarts
- **Applicable Scenarios**: User preferences, historical records, knowledge accumulation
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

The Agent can automatically call the `LoadMemory` tool to retrieve historical memory without manual handling.

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
- [VikingDB Documentation](https://www.volcengine.com/docs/84313/1860732?lang=en)

## License

This project is licensed under the Apache 2.0 License.
