# MCP Simple - MCP Protocol Tool Integration Example

This is an integration example based on Volcengine VeADK and AgentKit, demonstrating how to use the MCP (Model Context Protocol) to allow an Agent to call the Volcengine TOS (Tencent Object Storage) service.

## Overview

This example shows how an Agent can integrate MCP tools to achieve intelligent management of Volcengine Object Storage (TOS).

## Core Features

- Integrate Volcengine MCP Server as an Agent tool
- Operate object storage through natural language (list buckets, query files, read content, etc.)
- Use `MCPToolset` to manage tool connections and calls
- Demonstrate a production-level tool integration pattern

## Agent Capabilities

```text
User Natural Language Instructions
    ↓
AgentKit Runtime
    ↓
TOS MCP Agent
    ├── VeADK Agent (Dialogue Engine)
    ├── MCPToolset (Tool Manager)
    │   └── Volcengine TOS MCP Server
    │       ├── list_buckets
    │       ├── list_objects
    │       ├── get_object
    │       └── ... (More TOS operations)
    └── ShortTermMemory (Session Memory)
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/03_mcp_simple/agent.py) - The Agent application integrating MCP tools |
| **Test Client** | [client.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/03_mcp_simple/client.py) - SSE streaming invocation client |
| **Project Config** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/03_mcp_simple/pyproject.toml) - Dependency management (using uv) |
| **MCP Connection** | `MCPToolset` - Connects to the Volcengine MCP Server via HTTP |
| **Short-Term Memory** | Local backend for storing session context |

### Code Highlights

**MCP Tool Integration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/03_mcp_simple/agent.py#L8-L15)):

```python
url = os.getenv("TOOL_TOS_URL")

tos_mcp_runner = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=url,
        timeout=120
    ),
)
```

**Agent Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/03_mcp_simple/agent.py#L21-L26)):

```python
root_agent = Agent(
    name="tos_mcp_agent",
    instruction="You are an object storage management expert, proficient in various object storage operations using the MCP protocol.",
    tools=[tos_mcp_runner],
)
```

## Directory Structure

```bash
03_mcp_simple/
├── agent.py           # Agent application entry point (with MCP integration)
├── client.py          # Test client (SSE streaming invocation)
├── requirements.txt   # Python dependency list (required for agentkit deployment)
├── pyproject.toml     # Project configuration (uv dependency management)
├── .python-version    # Python version declaration (3.12)
├── agentkit.yaml      # AgentKit deployment configuration (auto-generated after running `agentkit config`)
├── Dockerfile         # Docker image build file (auto-generated after running `agentkit config`)
└── README.md          # Project documentation
```

## Running Locally

### Prerequisites

**1. Activate Volcengine Ark Model Service:**

- Visit the [Volcengine Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcengine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568) to get your AK/SK

**3. Get the TOS MCP Service URL:**

- Visit the [Volcengine MCP Marketplace](https://www.volcengine.com/mcp-marketplace)
- Find the [TOS MCP](https://www.volcengine.com/mcp-marketplace/detail?name=TOS%20MCP) service
- Get the service endpoint URL (which includes a token)

### Dependency Installation

#### 1. Install the `uv` Package Manager

```bash
# macOS / Linux (Official installation script)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use Homebrew (macOS)
brew install uv
```

#### 2. Initialize Project Dependencies

```bash
# Navigate to the project directory
cd python/01-tutorials/01-agentkit-runtime/03_mcp_simple
```

Use the `uv` tool to install the project dependencies:

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
# Volcengine Ark Model Name
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# Volcengine Access Credentials (Required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# TOS MCP Service URL (Required)
export TOOL_TOS_URL=https://tos.mcp.volcbiz.com/mcp?token=xxxxxx
```

**Note**: `TOOL_TOS_URL` must include the complete authentication token obtained from the Volcengine MCP Marketplace.

### Debugging Methods

#### Method 1: Command-Line Testing (Recommended for Beginners)

```bash
# Start the Agent service
uv run agent.py
# The service will listen on http://0.0.0.0:8000

# Open a new terminal and run the test client
# You need to edit client.py and change the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
uv run client.py
```

**Expected Output**:

```bash
[create session] Response from server: {"session_id": "agentkit_session"}
[run agent] Event from server:
data: {"event":"on_agent_start",...}
data: {"event":"on_tool_start","tool":"list_buckets"}
data: {"event":"on_llm_chunk","data":{"content":"You have the following buckets under your current account..."}}
```

#### Method 2: Using the VeADK Web Debugging Interface

```bash
# Go to the parent directory
cd python/01-tutorials/01-agentkit-runtime

# Start the VeADK Web interface
veadk web

# Access in your browser: http://127.0.0.1:8000
```

The web interface allows you to view the MCP tool call process and results in real-time.

## AgentKit Deployment

### Prerequisites

**Important**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the example runs correctly.

**1. Activate Volcengine Ark Model Service:**

- Visit the [Volcengine Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcengine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568) to get your AK/SK

**3. Get the TOS MCP Service URL:**

- Visit the [Volcengine MCP Marketplace](https://www.volcengine.com/mcp-marketplace)
- Find the [TOS MCP](https://www.volcengine.com/mcp-marketplace/detail?name=TOS%20MCP) service
- Get the service endpoint URL (which includes a token)

### AgentKit Cloud Deployment

```bash
cd python/01-tutorials/01-agentkit-runtime/03_mcp_simple

# Configure deployment parameters (requires setting the TOOL_TOS_URL environment variable)
agentkit config

# Launch the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'What buckets are under the current account?'

# Or use client.py to connect to the cloud service
# You need to edit client.py and change the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
# Modify client.py as needed, line 56, for the request content
uv run client.py
```

## Example Prompts

### Query Bucket List

```text
User: What buckets are under the current account?
Agent: Querying the bucket list...
      [Calling MCP tool: list_buckets]
      You have the following buckets under your current account:
      1. bucket-prod (Beijing region)
      2. bucket-dev (Shanghai region)
      3. bucket-backup (Guangzhou region)
```

### Query Object List

```text
User: What files are in bucket-prod?
Agent: Querying the file list for bucket-prod...
      [Calling MCP tool: list_objects]
      bucket-prod contains the following files:
      - data/users.csv (1.2MB)
      - images/logo.png (156KB)
      - files/config.txt (2KB)
```

### Read File Content

```text
User: Read the content of config.txt in the files directory of bucket-prod
Agent: Reading the file content...
      [Calling MCP tool: get_object]
      The content of config.txt is as follows:

      [System Config]
      version=1.0.0
      debug=false
      ...
```

### Complex Query

```text
User: Help me count the total number of files in all buckets
Agent: Okay, let me count them...
      [Calling MCP tool: list_buckets]
      [Calling MCP tool: list_objects (multiple times)]
      Count complete:
      - bucket-prod: 123 files
      - bucket-dev: 45 files
      - bucket-backup: 78 files
      Total: 246 files
```

## Demonstration

## Technical Points

### MCP Protocol Integration

**What is MCP**:

Model Context Protocol (MCP) is a standardized protocol for interaction between AI models and external tools/services.

**Integration Method**:

1. **Connection Configuration**:

```python
connection_params = StreamableHTTPConnectionParams(
    url="https://tos.mcp.volcbiz.com/mcp?token=xxx",
    timeout=120
)
```

2. **Tool Registration**:

```python
tos_mcp_runner = MCPToolset(connection_params=connection_params)
agent = Agent(tools=[tos_mcp_runner])
```

3. **Automatic Tool Discovery**: `MCPToolset` automatically discovers all tools provided by the MCP Server.

### Tool Call Flow

1. User inputs a natural language command.
2. The Agent understands the user's intent.
3. The Agent selects the appropriate MCP tool.
4. The MCP Server is called via HTTP.
5. The result from the tool is parsed.
6. A natural language response is generated.

### Differences from Regular Tools

| Feature | Regular Tool | MCP Tool |
| - | - | - |
| **Definition** | Defined directly as functions in code | Provided remotely via an MCP Server |
| **Discovery** | Requires manual registration | Automatically discovers all available tools |
| **Extensibility** | Requires code modification | Only requires updating the MCP Server |
| **Use Case** | Simple, local tools | Complex, remote services |

### Supported Operations by Volcengine TOS MCP

Common operations include:

- **Bucket Management**: `list_buckets`, `head_bucket`
- **Object Operations**: `list_objects`, `get_object`, `put_object`, `delete_object`
- **Object Attributes**: `head_object`, `copy_object`
- **Access Control**: `get_object_acl`, `set_object_acl`
- **More Operations**: Refer to the [TOS API Documentation](https://www.volcengine.com/docs/tos)

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcengine Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Volcengine MCP Marketplace](https://www.volcengine.com/mcp-marketplace)
- [TOS Object Storage Documentation](https://www.volcengine.com/docs/tos)

## License

This project is licensed under the Apache 2.0 License.
