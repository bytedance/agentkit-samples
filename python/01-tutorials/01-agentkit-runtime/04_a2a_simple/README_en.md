# A2A Simple - Agent-to-Agent Communication Protocol

This is an intelligent agent example built with Volcano Engine's VeADK and the A2A (Agent-to-Agent) protocol, demonstrating how to implement a standardized intelligent agent service.

## Overview

This example demonstrates the basic application of the A2A protocol, showing how to build an agent service that complies with the A2A protocol standard.

## Core Features

- A2A Protocol: A standardized communication protocol between intelligent agents.
- Agent Service: An A2A Agent that provides tool capabilities.
- Client Invocation: Invoking the Agent service through the A2A protocol.
- Tool Capabilities: Rolling dice and checking for prime numbers.
- State Management: Persisting state across tool calls.

## Agent Capabilities

```text
Client Invocation Flow
Local Client (local_client.py)
    ↓
A2A Protocol (HTTP/JSONRPC)
    ↓
Agent Service (agent.py:8000)
    ├── roll_die tool (Rolls a die)
    │   └── State Management: rolls history
    │
    └── check_prime tool (Checks for prime numbers)
```

## Directory Structure

```bash
04_a2a_simple/
├── agent.py                 # Agent service (port 8000)
├── local_client.py          # A2A client implementation
├── tools/                   # Tool implementations
│   ├── roll_die.py         # Die rolling tool
│   └── check_prime.py      # Prime number checking tool
├── agentkit.yaml           # AgentKit deployment configuration
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project configuration
├── Dockerfile              # Docker image build file
└── README.md               # Project documentation
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/agent.py) - `hello_world_agent`, provides tool services (port 8000). |
| **Local Client** | [local_client.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/local_client.py) - `A2ASimpleClient`, invokes the Agent service. |
| **Tool: roll_die** | [tools/roll_die.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/tools/roll_die.py) - Rolls a die. |
| **Tool: check_prime** | [tools/check_prime.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/tools/check_prime.py) - Checks for prime numbers. |
| **AgentCard** | Agent metadata and capability description. |
| **Project Configuration** | [agentkit.yaml](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/agentkit.yaml) - AgentKit deployment configuration. |

### Code Highlights

**Agent Definition** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/agent.py#L9-L35)):

```python
root_agent = Agent(
    name="hello_world_agent",
    description=(
        "hello world agent that can roll a dice of 8 sides and check prime numbers."
    ),
    instruction="""
      You roll dice and answer questions about the outcome of the dice rolls.
      You can roll dice of different sizes.
      You can use multiple tools in parallel by calling functions in parallel(in one request and in one round).
      It is ok to discuss previous dice roles, and comment on the dice rolls.
      When you are asked to roll a die, you must call the roll_die tool with the number of sides. Be sure to pass in an integer. Do not pass in a string.
      You should never roll a die on your own.
      When checking prime numbers, call the check_prime tool with a list of integers. Be sure to pass in a list of integers. You should never pass in a string.
      You should not check prime numbers before calling the tool.
      When you are asked to roll a die and check prime numbers, you should always make the following two function calls:
      1. You should first call the roll_die tool to get a roll. Wait for the function response before calling the check_prime tool.
      2. After you get the function response from roll_die tool, you should call the check_prime tool with the roll_die result.
        2.1 If user asks you to check primes based on previous rolls, make sure you include the previous rolls in the list.
      3. When you respond, you must include the roll_die result from step 1.
      You should always perform the previous 3 steps when asking for a roll and checking prime numbers.
      You should not rely on the previous history on prime results.
    """,
    tools=[
        roll_die,
        check_prime,
    ],
)
```

**AgentCard Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/agent.py#L45-L55)):

```python
agent_card = AgentCard(
    capabilities=AgentCapabilities(streaming=True),
    description=root_agent.description,
    name=root_agent.name,
    default_input_modes=["text"],
    default_output_modes=["text"],
    provider=AgentProvider(organization="agentkit", url=""),
    skills=[AgentSkill(id="0", name="chat", description="Chat", tags=["chat"])],
    url="http://localhost:8000",
    version="1.0.0",
)
```

**Local Client Invocation** ([local_client.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/local_client.py#L28-L88)):

```python
async def create_task(self, agent_url: str, message: str) -> str:
    # Get Agent Card
    agent_card_response = await httpx_client.get(
        f'{agent_url}{AGENT_CARD_WELL_KNOWN_PATH}'
    )
    agent_card = AgentCard(**agent_card_response.json())

    # Create A2A client
    factory = ClientFactory(config)
    client = factory.create(agent_card)

    # Send message
    async for response in client.send_message(message_obj):
        responses.append(response)
```

**Tool State Management** ([tools/roll_die.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/tools/roll_die.py#L6-L21)):

```python
def roll_die(sides: int, tool_context: ToolContext) -> int:
    result = random.randint(1, sides)

    # State persistence
    if "rolls" not in tool_context.state:
        tool_context.state["rolls"] = []

    tool_context.state["rolls"] = tool_context.state["rolls"] + [result]
    return result
```

## Local Execution

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

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
cd python/01-tutorials/01-agentkit-runtime/04_a2a_simple
```

Use `uv` to install the project dependencies:

```bash
# If you don't have a `uv` virtual environment, create one first
uv venv --python 3.12

# Activate the virtual environment
source .venv/bin/activate

# Use `pyproject.toml` to manage dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Environment Setup

```bash
# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Debugging Methods

#### Method 1: Using the VeADK Web Debugging Interface

```bash
# Go to the parent directory
cd python/01-tutorials/01-agentkit-runtime

# Start the VeADK Web interface
veadk web

# Access in your browser: http://127.0.0.1:8000
```

The web interface provides a graphical chat environment for testing and supports real-time viewing of the invocation process.

#### Method 2: Command-Line Testing (Recommended for Learning)

**Step 1: Start the Agent Service:**

```bash
# Run in terminal window 1
cd python/01-tutorials/01-agentkit-runtime/04_a2a_simple
uv run agent.py

# After the service starts, you can access the Agent Card
# http://localhost:8000/.well-known/agent-card.json
```

**Step 2: Run the Local Client:**

```bash
# Run in terminal window 2
cd python/01-tutorials/01-agentkit-runtime/04_a2a_simple
python local_client.py
```

## AgentKit Deployment

### Prerequisites

**Important Note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the case can execute normally.

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get your AK/SK

### AgentKit Cloud Deployment

```bash
cd python/01-tutorials/01-agentkit-runtime/04_a2a_simple

# Configure deployment parameters (Important: agent_type must be a2a)
agentkit config

# View configuration
agentkit config --show

# Launch the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'Hello, show me one number.'
```

**Important Note:**

- Make sure the `common.agent_type` in `agentkit.yaml` is set to `a2a`.
- Otherwise, you will not be able to successfully deploy an A2A-type Agent.

## Example Prompts

### Basic Capability Test

**Roll a die**:

```text
User: Hello, show me one number.
Agent: I'll roll a die for you.
      [Invokes roll_die(sides=6)]
      I rolled a 4.
```

### Composite Task

**Roll multiple times and count:**

```text
User: Please roll 10 times, show counts, and tell me which results are prime.
Agent: [Invokes roll_die 10 times consecutively]
      Results: 3, 7, 2, 5, 8, 1, 9, 4, 6, 3
      [Invokes check_prime([3, 7, 2, 5, 8, 1, 9, 4, 6, 3])]
      Prime numbers found: 2, 3, 5, 7
```

### Specify Parameters

**Custom number of sides for the die:**

```text
User: Roll a 12-sided die.
Agent: [Invokes roll_die(sides=12)]
      I rolled an 8 on a 12-sided die.
```

### State Memory

**Query history:**

```text
User: Show previous roll history.
Agent: [Reads tool_context.state['rolls']]
      Your previous rolls: [4, 8, 3, 7, 2]
```

### Actual Runtime Output

Example output from running `local_client.py`:

```text
5 are prime numbers.
No prime numbers found.
3 are prime numbers.
5 are prime numbers.
2 are prime numbers.
5 are prime numbers.
3 are prime numbers.
5 are prime numbers.
5 are prime numbers.
3 are prime numbers.
```

## Effect Demonstration

## Technical Points

### A2A Protocol

- **Standardized Communication**: A standardized communication protocol between Agents.
- **Agent Card**: Describes the metadata and capabilities of an Agent.
- **Transport Protocol**: Supports HTTP/JSON and JSONRPC.
- **Interoperability**: Agents with different implementations can call each other.

### Agent Card

The Agent Card provides the following information:

- **Basic Information**: Name, description, version.
- **Capabilities**: Supported features (e.g., streaming output).
- **Skills**: Tasks the Agent can perform.
- **Interfaces**: Input/output modes (text, image, etc.).

How to access:

```bash
# Agent Card
http://localhost:8000/.well-known/agent-card.json
```

### Tool State Management

`ToolContext.state`

- Persists state between tool calls.
- Supports complex state management logic.
- Example: Recording roll history.

```python
tool_context.state["rolls"] = tool_context.state["rolls"] + [result]
```

### Invocation Flow

**Client Invocation Flow (local_client.py):**

1. **Get Agent Card**: Understand the Agent's capabilities.
2. **Create Client**: Create an A2A client based on the Agent Card.
3. **Send Message**: Send a request via the A2A protocol.
4. **Receive Response**: Process the Agent's response.

### AgentKit A2A App

```python
from agentkit.apps import AgentkitA2aApp
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor

a2a_app = AgentkitA2aApp()

@a2a_app.agent_executor(runner=runner)
class MyAgentExecutor(A2aAgentExecutor):
    pass

a2a_app.run(agent_card=agent_card, host="0.0.0.0", port=8000)
```

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [A2A Protocol Specification](https://github.com/google/adk)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## License

This project is licensed under the Apache 2.0 License.
