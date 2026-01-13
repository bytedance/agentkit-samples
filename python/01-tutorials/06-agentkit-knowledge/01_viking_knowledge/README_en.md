# viking knowledge - Intelligent Q&A for Document Knowledge Base

This is a RAG (Retrieval-Augmented Generation) example built with Volcano Engine VeADK and VikingDB, demonstrating how to implement intelligent Q&A for a professional document knowledge base through vector retrieval.

## Overview

This example shows how to use VikingDB to build a document knowledge base and create a professional Q&A system based on real document content.

## Core Features

- Directly import documents without manual slicing.
- Automatically build vector indexes.
- Enhance answer accuracy with semantic retrieval.
- Support composite queries from multiple document sources.

## Agent Capabilities

```text
User Query
    ↓
Agent (Knowledge Q&A)
    ↓
VikingDB Retrieval
    ├── Vector Index Query
    ├── Document Content Retrieval
    └── Relevance Ranking
    ↓
LLM Generates Answer
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge/agent.py) - The main application that integrates KnowledgeBase and VikingDB. |
| **Knowledge Base** | VikingDB vector database, storing document vector indexes. |
| **Document Sources** | tech.txt (technical documents), products.txt (product information). |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge/pyproject.toml) - Dependency management (uv tool). |
| **Short-term Memory** | Maintains session context. |

### Code Features

**Knowledge Base Creation** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge/agent.py#L22-L29)):

```python
# Prepare knowledge sources
with open("/tmp/product_info.txt", "w") as f:
    f.write("Product List and Prices:\n1. High-Performance Laptop (Laptop Pro) - Price: 8999 yuan...")
with open("/tmp/service_policy.txt", "w") as f:
    f.write("After-Sales Service Policy:\n1. Warranty Period: All electronic products come with a 1-year free warranty...")

# Create knowledge base
kb = KnowledgeBase(backend="viking", app_name="test_app")
kb.add_from_files(files=["/tmp/product_info.txt", "/tmp/service_policy.txt"])
```

**Agent Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge/agent.py#L31-L36)):

```python
root_agent = Agent(
    name="test_agent",
    knowledgebase=kb,
    instruction="You are a helpful assistant. Be concise and friendly.",
)
```

## Directory Structure

```text
01_viking_knowledge/
├── agent.py           # Agent application entry point (integrates VikingDB)
├── requirements.txt   # Python dependency list
├── pyproject.toml     # Project configuration (uv dependency management)
└── README.md          # Project documentation
```

## Local Execution

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service.

**2. Activate VikingDB Service:**

- Visit the [VikingDB Console](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- Create a knowledge base/Collection.

**3. Activate Object Storage Service (TOS):**

- VikingDB needs to upload local files to TOS, so you need to activate the object storage service.
- Visit the [TOS Console](https://console.volcengine.com/tos)

**4. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get your AK/SK.

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
cd python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge
```

Use the `uv` tool to install project dependencies:

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

#### Method 1: Use VeADK Web Debugging Interface

```bash
# Go to the parent directory
cd python/01-tutorials/06-agentkit-knowledge

# Start the VeADK Web interface
veadk web

# Visit in your browser: http://127.0.0.1:8000
```

The web interface provides a graphical dialogue testing environment, supporting real-time viewing of retrieval results and debugging information.

#### Method 2: Command-line Testing

```bash
# Start the Agent service
uv run agent.py
# The service will listen on http://0.0.0.0:8000
```

**Important Note**: When inserting documents into VikingDB for the first time, it needs to build a vector index (takes about 2-5 minutes). The first run may result in an error; please wait for the index to be built and try again.

## AgentKit Deployment

### Prerequisites

**Important Note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the case can be executed normally.

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service.

**2. Activate VikingDB Service:**

- Visit the [VikingDB Console](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- Create a knowledge base/Collection.

**3. Activate Object Storage Service (TOS):**

- VikingDB needs to upload local files to TOS, so you need to activate the object storage service.
- Visit the [TOS Console](https://console.volcengine.com/tos)

**4. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get your AK/SK.

### AgentKit Cloud Deployment

```bash
# Enter the project directory
cd python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge

# Configure deployment parameters. The DATABASE_TOS_BUCKET environment variable needs to be passed to the Agent to upload local files to TOS, which are then imported into the knowledge base.
agentkit config \
--agent_name vikingdb_agent \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-2107625663 \
--runtime_envs DATABASE_VIKING_COLLECTION=agentkit_knowledge_app \
--launch_type cloud

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'What is the price of the High-Performance Laptop PRO?'

# Or use client.py to connect to the cloud service
# You need to edit client.py, changing the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml.
# Modify the request content in client.py on line 56 as needed.
uv run client.py
```

## Example Prompts

### Product Information Query

**Retrieval-based answers from product_info.txt**:

```text
User: What is the price of the High-Performance Laptop Pro?
Agent: According to the product list, the price of the High-Performance Laptop (Laptop Pro) is 8999 yuan.

User: What is the cheapest product here?
Agent: The cheapest product is the Tablet Air, priced at 2999 yuan.
```

### After-Sales Service Query

**Data retrieval from service_policy.txt**:

```text
User: What is your return and exchange policy?
Agent: According to the after-sales service policy, we support no-reason returns within 7 days of purchase and exchanges for quality issues within 15 days.

User: How long is the warranty for the laptop?
Agent: All electronic products come with a 1-year free warranty.
```

### Contextual Query

**Continuous Q&A reusing previous context:**

```text
User: What about the SmartPhone X?
Agent: The price of the SmartPhone X is 4999 yuan.
```

### Composite Query

**Comprehensive query across documents:**

```text
User: I want to buy a device for both work and entertainment. What do you recommend, and what is the after-sales support?
Agent: I recommend the Tablet Air. It is thin, portable, and suitable for both work and entertainment, priced at 2999 yuan. For after-sales support, we offer a 1-year free warranty and support 7-day no-reason returns.
```

## Effect Demonstration

## Technical Points

### VikingDB Knowledge Base

- **Storage Method**: Vector database (`backend="viking"`)
- **Document Import**: Supports direct import of multiple files.
- **Automatic Indexing**: Automatically builds vector indexes (requires 2-5 minutes for the first time).
- **Retrieval Method**: Vector retrieval based on semantic similarity.
- **Applicable Scenarios**: Document knowledge bases, professional Q&A, RAG applications.

### RAG Workflow

1. **Document Preparation**: Write document content to files.
2. **Vectorization**: KnowledgeBase automatically converts documents into vectors.
3. **Storage**: Vectors are stored in VikingDB.
4. **Retrieval**: Retrieve relevant document snippets when a user queries.
5. **Generation**: LLM generates an answer based on the retrieved content.

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
- [VikingDB Documentation](https://www.volcengine.com/docs/84313/1860732?lang=zh)

## Code License

This project is licensed under the Apache 2.0 License.
