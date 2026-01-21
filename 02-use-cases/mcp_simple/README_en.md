# MCPSimpleAgent - MCP Protocol Tool Integration Example

An MCP (Model Context Protocol) integration example built on Volcengine VeADK and AgentKit, demonstrating how to call the MCP toolset via `mcp_router`.

## Overview

This example demonstrates how an Agent integrates and schedules the MCP toolset through the built-in `mcp_router` tool. The Agent is configured as an assistant with deep reasoning capabilities, capable of automatically routing to the corresponding MCP tools to complete tasks based on user intent.

## Core Features

- Integrate Volcengine MCP Server as an Agent tool
- User natural language instructions, agent calls MCP toolset to complete tasks.
- Use MCPToolset to manage tool connections and calls
- Demonstrate production-level tool integration patterns

## Agent Capabilities

```text
User Natural Language Instructions
    ↓
AgentKit Runtime
    ↓
TOS MCP Agent
    ├── VeADK Agent (Dialogue Engine)
    ├── MCPToolset (Tool Manager)
    │   └── mcp_search_tool (Search Tool)
    │   └── mcp_use_tool (Use Tool)
    │ 
    └── ShortTermMemory (Session Memory)
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/mcp_simple/agent.py) - Agent application integrating MCP tools |
| **Test Client** | [client.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/mcp_simple/client.py) - SSE streaming client |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/mcp_simple/pyproject.toml) - Dependency management (uv tool) |
| **Short Term Memory** | Local backend storage for session context |

### Code Features

**Agent Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/mcp_simple/agent.py#L10-L20)):

```python
root_agent = Agent(
    name="mcp_agent",
    instruction="You are an AI assistant with deep reasoning capabilities. When you encounter complex logic, mathematics, programming, or problems requiring multi-step reasoning, please make sure to use MCP tools to assist in completing user questions.",
    tools=[mcp_router],  # Integrate MCP router tool
    model_extra_config={
        "extra_body": {
            "thinking": {"type": "disabled"}
        }
    },
)
```

## Directory Structure

```bash
mcp_simple/
├── agent.py           # Agent application entry point
├── client.py          # Test client
├── requirements.txt   # Python dependency list
├── pyproject.toml     # Project configuration (uv dependency management)
└── README.md          # Project documentation
```

## Run Locally

### Prerequisites

**1. Activate Volcengine Ark Model Service**
- Visit [Volcengine Ark Console](https://exp.volcengine.com/ark?mode=chat) and activate the service.

**2. Get Access Credentials**
- Refer to [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get AK/SK.

**3. Prepare MCP Service**
- Refer to [Volcengine MCP Toolset](https://www.volcengine.com/docs/86681/1844858?lang=zh) to configure and start the MCP service, create the MCP toolset, and obtain the URL and API Key.

### Install Dependencies

#### 1. Install uv Package Manager

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. Initialize Project Dependencies

```bash
cd python/01-tutorials/01-agentkit-runtime/mcp_simple

# Create virtual environment and install dependencies
uv venv --python 3.12
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
source .venv/bin/activate
```

### Environment Configuration

```bash
# Volcengine Ark Model Name
export MODEL_AGENT_NAME=doubao-seed-1-8-251228

# Volcengine Access Credentials
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# Volcengine MCP Toolset Address and Access Credentials
export TOOL_MCP_ROUTER_URL=https://*****.apigateway-cn-****.volceapi.com/mcp
export TOOL_MCP_ROUTER_API_KEY=<Your API Key>
```

### Debugging Methods

#### 1. Start Agent Service

```bash
uv run agent.py
```

#### 2. Run Test Client

```bash
# Run client
uv run client.py
```

**Run Result Example**:

```text
[run agent] Event from server:
[create session] Response from server: {'id': 'agentkit_session', 'appName': 'mcp_agent', 'userId': 'agentkit_user', 'state': {}, 'events': [], 'lastUpdateTime': 1768465256.520708}
data: {"modelVersion":"doubao-seed-1-8-251228"...
...
```

#### 3. Use VeADK Web Debugging

```bash
cd python/01-tutorials/01-agentkit-runtime
veadk web
# Visit http://127.0.0.1:8000
```

## AgentKit Deployment

### Cloud Deployment Process

**1. Authorization and Preparation**
Ensure that service authorization is completed in the [AgentKit Console](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default).

**2. Deployment Commands**

```bash
cd python/01-tutorials/01-agentkit-runtime/mcp_simple

# Generate/Update configuration
agentkit config
Note: Application-level runtime environment variables need to configure three environment variables: MODEL_AGENT_NAME, TOOL_MCP_ROUTER_URL, and TOOL_MCP_ROUTER_API_KEY
# Launch cloud service
agentkit launch

# Command line test
agentkit invoke 'A frog can jump 1 step or 2 steps at a time. To jump up a 10-step staircase, how many ways are there in total? What if it is n steps?'
```

**3. Use Client to Connect to Cloud**
Modify `base_url` and `api_key` in `client.py` to `runtime_endpoint` and `runtime_apikey` generated in `agentkit.yaml`, then run:

```bash
uv run client.py
```

## Technical Highlights

### `mcp_router` Tool

`mcp_router` is a general MCP routing tool provided by the VeADK framework. It is not just a single tool, but a gateway capable of perceiving and distributing requests to multiple MCP Servers.

- **Automatic Routing**: Automatically selects appropriate MCP tools based on user instructions.
- **Protocol Encapsulation**: Shields underlying MCP protocol details (such as JSON-RPC message formats).
- **Unified Interface**: The Agent only needs to interact with `mcp_router` without managing each MCP connection individually.

### Deep Reasoning Configuration

The Agent specifies `instruction` in the configuration to emphasize deep reasoning capabilities:

```python
instruction="You are an AI assistant with deep reasoning capabilities... please make sure to use MCP tools to assist in completing user questions."
```

This guides the model to actively think and use external tools (via MCP) to solve problems when facing complex issues, rather than answering solely based on training data.

## FAQ
None

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcengine Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Volcengine MCP Marketplace](https://www.volcengine.com/mcp-marketplace)
- [TOS Object Storage Documentation](https://www.volcengine.com/docs/tos)

## Code License

This project follows the Apache 2.0 License
