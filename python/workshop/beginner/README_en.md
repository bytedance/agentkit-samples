# Beginner Case Collection - AgentKit Getting Started Examples

Welcome to the AgentKit Beginner Case Collection! This directory contains a series of Agent development examples, from basic to advanced, to help you quickly master the core features of Volcano Engine VeADK and the AgentKit platform.

## 📚 Case Overview

### Basic Introduction

| Case | Description | Core Capabilities |
| - | - | - |
| **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)** | The simplest conversational Agent | Basic conversation, short-term memory |
| **[Callback](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/callback)** | Agent callback and guardrail demonstration | Lifecycle callbacks, content moderation, PII filtering |

### Tool Integration

| Case | Description | Core Capabilities |
| - | - | - |
| **[MCP Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple)** | MCP protocol tool integration | MCP tools, object storage management |
| **[Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge)** | Travel itinerary planning assistant | Web search, professional instruction system |
| **[Restaurant Ordering](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/restaurant_ordering)** | Restaurant ordering assistant | Asynchronous tools, parallel calls, context compression |

### Memory and Knowledge Base

| Case | Description | Core Capabilities |
| - | - | - |
| **[VikingDB](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingdb)** | Knowledge base retrieval augmentation | RAG, vector retrieval, document Q&A |
| **[VikingMem](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingmem)** | Long and short-term memory management | Short-term memory, long-term memory, cross-session memory |

### Multi-Agent

| Case | Description | Core Capabilities |
| - | - | - |
| **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents)** | Multi-agent collaboration system | Sequential execution, parallel execution, loop optimization |
| **[A2A Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/a2a_simple)** | Agent-to-Agent communication | A2A protocol, remote Agent invocation |

### Content Generation

| Case | Description | Core Capabilities |
| - | - | - |
| **[Episode Generation](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/episode_generation)** | Image and video generation | Sub-Agent, image generation, video generation |

## 🚀 Quick Start

### Prerequisites

**Important Note**: Before running any examples, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the cases can execute properly.

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat) to activate the model service.

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=en) to get your AK/SK.

**3. Install Necessary Tools:**

```bash
# Install uv package manager (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use Homebrew (macOS)
brew install uv

# Install VeADK Python SDK
pip install --upgrade veadk-python

# Install AgentKit Python SDK (for deploying to the AgentKit platform)
pip install --upgrade agentkit-sdk-python
```

### Unified Debugging Method

In the `beginner` directory, you can use a unified method to debug most cases:

```bash
# Export environment variables required for all cases
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
export TOOL_TOS_URL=https://tos.mcp.volcbiz.com/mcp\?token\=xxxxx  # Optional, only needed for mcp_simple

# Navigate to the root directory of the beginner cases
cd 02-use-cases/beginner

# Install dependencies for all cases (using uv)
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Start the VeADK Web debugging interface
veadk web --port 8080

# Access in your browser: http://127.0.0.1:8080
```

With the VeADK Web interface, you can:

- Select any case for interactive testing
- View the Agent execution flow in real-time
- Debug tool calls and their return results
- View logs and performance metrics

**Notes**:

Some cases require additional configuration to run properly in VeADK Web:

- **a2a_simple**: Not suitable for debugging in VeADK Web as it requires starting a remote Agent service first. Please refer to the case's README for command-line execution.
- **mcp_simple**: Requires the `TOOL_TOS_URL` environment variable (MCP service address) to be configured first. The Agent can still be loaded without it, but the tool will be unavailable.
- **vikingmem**: Requires the VikingDB service to be activated. It is recommended to configure the `VIKINGMEM_APP_NAME` environment variable first (defaults to `vikingmem_test_app`).
- **vikingdb**: Requires VikingDB and TOS services to be activated. The first run may take 2-5 minutes to build the vector index.

### Individual Debugging and Deployment

Enter each case directory to:

#### 1. Local Development and Debugging

```bash
cd <case_directory>

# Initialize virtual environment and install dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Activate virtual environment
source .venv/bin/activate

# Configure environment variables
export MODEL_AGENT_NAME=doubao-seed-1-6-251015
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# Run the Agent service
uv run agent.py
```

#### 2. Deploy to AgentKit Platform

```bash
cd <case_directory>

# Configure deployment parameters
agentkit config

# Launch the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'your test prompt'
```

## 📖 Learning Paths

### Path 1: Basic Introduction (Recommended for Beginners)

1. **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)** - Understand the basic structure of an Agent and short-term memory.
2. **[Callback](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/callback)** - Master callback mechanisms and guardrail functions.
3. **[Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge)** - Learn tool integration and professional instructions.
4. **[VikingDB](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingdb)** - Practice knowledge base retrieval augmentation.

### Path 2: Tools and Integration

1. **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)** - Basic knowledge.
2. **[MCP Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple)** - MCP protocol tool integration.
3. **[Restaurant Ordering](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/restaurant_ordering)** - Asynchronous tools and parallel calls.
4. **[Episode Generation](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/episode_generation)** - Content generation tools.

### Path 3: Multi-Agent Systems

1. **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)** - Single Agent basics.
2. **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents)** - Multi-agent collaboration models.
3. **[A2A Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/a2a_simple)** - Inter-Agent communication.
4. **[VikingMem](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingmem)** - Cross-session memory management.

## 🔍 Detailed Case Explanations

### Hello World - Basic Conversational Agent

The simplest introductory example, demonstrating:

- How to create a basic Agent
- How to use short-term memory to maintain conversation context
- How to implement multi-turn conversations

**Target Audience**: All beginners

**Learning Time**: 15 minutes

**Key Code**:

```python
agent = Agent()
short_term_memory = ShortTermMemory(backend="local")
runner = Runner(agent=agent, short_term_memory=short_term_memory)
```

### Callback - Callbacks and Guardrails

An in-depth look at the Agent lifecycle, demonstrating:

- The use of six major callback functions
- Input and output guardrail mechanisms
- PII information filtering
- Parameter validation and result post-processing

**Target Audience**: Developers who need to implement content moderation and security controls.

**Learning Time**: 30 minutes

**Key Capabilities**: `before_agent_callback`, `after_model_callback`, `before_tool_callback`

### MCP Simple - Tool Protocol Integration

Learn the MCP protocol, demonstrating:

- How to integrate an MCP Server
- How to operate object storage through natural language
- Automatic tool discovery and invocation

**Target Audience**: Developers who need to integrate external services.

**Learning Time**: 30 minutes

**Key Technologies**: `MCPToolset`, `StreamableHTTPConnectionParams`

### Travel Concierge - Professional Domain Agent

Build a professional travel planner, demonstrating:

- A detailed professional instruction system
- Use of web search tools
- Workflow design for complex tasks

**Target Audience**: Developers who need to build domain expert Agents.

**Learning Time**: 45 minutes

**Key Techniques**: Role definition, workflow, constraints, output format

### Restaurant Ordering - Advanced Tool Usage

A restaurant ordering assistant, demonstrating:

- Asynchronous tools and parallel calls
- Context management and compression
- Tool state management
- Custom plugins

**Target Audience**: Developers who need to optimize performance and handle long conversations.

**Learning Time**: 60 minutes

**Key Technologies**: `EventsCompactionConfig`, `ContextFilterPlugin`, `ToolContext.state`

### VikingDB - Knowledge Base Retrieval

An RAG practice example, demonstrating:

- Document import and vector indexing
- Knowledge base retrieval
- Knowledge-based Q&A

**Target Audience**: Developers who need to build knowledge base Q&A systems.

**Learning Time**: 45 minutes

**Key Components**: `KnowledgeBase`, `Viking` backend

### VikingMem - Memory Management

A memory system practice, demonstrating:

- Short-term memory (single session)
- Long-term memory (cross-session)
- Memory persistence and retrieval

**Target Audience**: Developers who need to implement user personalization and history.

**Learning Time**: 40 minutes

**Key Components**: `ShortTermMemory`, `LongTermMemory`, `save_session_to_long_term_memory`

### Multi Agents - Multi-Agent Collaboration

A multi-Agent system, demonstrating:

- Three collaboration modes (sequential, parallel, loop)
- Hierarchical Agent architecture
- Specialization and task distribution

**Target Audience**: Developers who need to build complex collaborative systems.

**Learning Time**: 90 minutes

**Key Components**: `SequentialAgent`, `ParallelAgent`, `LoopAgent`

### Episode Generation - Content Generation

Image and video generation, demonstrating:

- Use of sub-Agents
- Image generation tools
- Video generation tools
- Toolchain orchestration

**Target Audience**: Developers who need to implement multimodal content generation.

**Learning Time**: 45 minutes

**Key Tools**: `image_generate`, `video_generate`, `web_search`

### A2A Simple - Inter-Agent Communication

Agent-to-Agent protocol, demonstrating:

- A2A protocol implementation
- Remote Agent invocation
- Agent card configuration
- Distributed Agent systems

**Target Audience**: Developers who need to build distributed Agent systems.

**Learning Time**: 60 minutes

**Key Components**: `RemoteVeAgent`, `AgentkitA2aApp`, `AgentCard`

## 💡 FAQ

### Q1: Which case should I start with?

**A**: It is highly recommended to start with [Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world), as it covers the most basic Agent creation and memory management. After that, choose based on your needs:

- Need content moderation → [Callback](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/callback)
- Need tool integration → [MCP Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple) or [Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge)
- Need a knowledge base → [VikingDB](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingdb)
- Need multiple Agents → [Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents)

### Q2: Why won't my case run?

**A**: Please check the following:

1. Have you visited the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize services?
2. Are the environment variables (`MODEL_AGENT_NAME`, `VOLCENGINE_ACCESS_KEY`, `VOLCENGINE_SECRET_KEY`) configured correctly?
3. Are the necessary dependencies (`veadk-python`, `agentkit-sdk-python`) installed?
4. For cases requiring VikingDB, has it been activated and a knowledge base created?

### Q3: What is the difference between VeADK Web and the AgentKit platform?

**A**:

- **VeADK Web**: A local debugging tool with a graphical interface for quickly testing Agents without deployment.
- **AgentKit Platform**: A cloud deployment platform providing production-level deployment, monitoring, version management, etc.

Recommended workflow: Local development → VeADK Web debugging → AgentKit platform deployment.

### Q4: How do I deploy to a production environment?

**A**: For production deployment, it is recommended to use the AgentKit platform:

```bash
agentkit config
agentkit launch
```

**Note**: Production environments must enable key authentication and configure IAM roles.

### Q5: How do I monitor the performance and logs of my Agent?

**A**: You can view performance and logs in the following ways:

- **Local Development**: Check console output and log files.
- **VeADK Web**: View the execution flow and tool calls in real-time.
- **AgentKit Platform**: Provides complete monitoring, logging, and tracing functions.
- **Custom Monitoring**: Use the callback mechanism to implement custom metric collection.

### Q6: Are there dependencies between the cases?

**A**: The cases are relatively independent, but it is recommended to follow the learning paths. Some advanced cases use concepts from basic cases:

- `Multi Agents` is based on the Agent concept from `Hello World`.
- `VikingMem` extends the memory management from `Hello World`.
- `Restaurant Ordering` combines several basic concepts.

## 🎯 Next Steps

After completing the Beginner cases, you can:

1. **Explore Advanced Cases**: Check out the other directories under `02-use-cases/`.
2. **Read the Official Documentation**: Dive deeper into the advanced features of VeADK and AgentKit.
3. **Build Your Own Agent**: Apply what you've learned to your own projects.
4. **Join the Community**: Exchange experiences with other developers.

## 📖 References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [VikingDB Documentation](https://www.volcengine.com/docs/84313/1860732?lang=en)
- [MCP Protocol Specification](https://modelcontextprotocol.io)

## 🤝 Contributing

Contributions to improve these examples are welcome via Issues and Pull Requests!

---

**Happy learning! If you have any questions, please refer to the README of each case or contact technical support.**
