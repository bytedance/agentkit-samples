# Restaurant Ordering - Smart Assistant for Restaurant Ordering

This is an advanced ordering Agent built based on Volcano Engine's VeADK, demonstrating advanced features such as complex business processes, asynchronous tool calls, context management, and custom plugins.

## Overview

This example is a fully functional restaurant ordering assistant that showcases several advanced capabilities of VeADK.

## Core Features

- Asynchronous tools and parallel calls: Process multiple dish orders simultaneously
- Advanced context management: Event compression and context filtering
- State management: Maintain order status using ToolContext
- Custom plugins: Monitor Agent invocations and LLM calls
- Web search integration: Handle special requests not on the menu

## Agent Capabilities

```text
User's order request
    ↓
Restaurant Ordering Agent
    ├── Menu matching (semantic understanding)
    ├── Parallel tool calls
    │   ├── add_to_order (add dish)
    │   ├── summarize_order (summarize order)
    │   └── web_search (off-menu search)
    │
    ├── State management (ToolContext)
    │   └── order: [] (order list)
    │
    └── Plugin system
        ├── CountInvocationPlugin (counting plugin)
        ├── ContextFilterPlugin (context filtering)
        └── EventsCompactionConfig (event compression)
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L82-L117) - order_agent, the ordering assistant |
| **Test Script** | [main.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/main.py) - Complete ordering process demonstration |
| **Custom Tools** | add_to_order, summarize_order |
| **Custom Plugin** | CountInvocationPlugin - Counts invocation times |
| **Context Management** | EventsCompactionConfig + ContextFilterPlugin |

### Code Features

**Asynchronous Tool Definition** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L52-L79)):

```python
async def add_to_order(dish_name: str, tool_context: ToolContext = None) -> str:
    """Adds a dish to the user's order."""
    if "order" not in tool_context.state:
        tool_context.state["order"] = []

    tool_context.state["order"] = tool_context.state["order"] + [dish_name]
    return f"I've added {dish_name} to your order."

async def summarize_order(tool_context: ToolContext = None) -> str:
    """Summarizes the user's current order."""
    order = tool_context.state.get("order", [])
    if not order:
        return "You haven't ordered anything yet."

    summary = "Here is your order so far:\n" + "\n".join(f"- {dish}" for dish in order)
    return summary
```

**Agent Configuration and Parallel Calls** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L82-L117)):

```python
order_agent = Agent(
    name="restaurant_ordering_agent",
    description="An agent that takes customer orders at a restaurant.",
    instruction=f"""
        You are a friendly and efficient order-taking assistant for a restaurant.
        The menu contains: {", ".join(RECIPES)}.

        **Workflow:**
        1. Understand the user's request and match to menu items.
        2. You MUST call the `add_to_order` tool. You can using parallel invocations
           to add multiple dishes to the order.
        3. Handle off-menu requests using `web_search` tool.
        4. When finished, call `summarize_order` tool.
    """,
    tools=[add_to_order, summarize_order, web_search],
)
```

**Custom Plugin** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L120-L144)):

```python
class CountInvocationPlugin(BasePlugin):
    """A custom plugin that counts agent and tool invocations."""

    def __init__(self) -> None:
        super().__init__(name="count_invocation")
        self.agent_count: int = 0
        self.llm_request_count: int = 0

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        self.agent_count += 1
        print(f"[Plugin] Agent run count: {self.agent_count}")

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> None:
        self.llm_request_count += 1
        print(f"[Plugin] LLM request count: {self.llm_request_count}")
```

**Context Management Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L151-L167)):

```python
app = App(
    name="restaurant_ordering",
    root_agent=root_agent,
    plugins=[
        CountInvocationPlugin(),
        ContextFilterPlugin(num_invocations_to_keep=8),  # Keep the last 8 rounds of conversation
        SaveFilesAsArtifactsPlugin(),
    ],
    # Event compression: trigger compression every 3 calls
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1,
    ),
)
```

## Directory Structure

```bash
08_restaurant_ordering/
├── agent.py           # Agent application entry point (advanced features example)
├── main.py            # Complete ordering process demonstration script
├── requirements.txt   # Python dependency list (required for agentkit deployment)
└── README.md          # Project documentation
```

## Local Execution

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get AK/SK

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
cd python/02-use-cases/08_restaurant_ordering
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
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Debugging Methods

#### Method 1: Use VeADK Web Debugging Interface

```bash
# Go to the parent directory
cd ..

# Start the VeADK Web interface
veadk web

# Visit in your browser: http://127.0.0.1:8000
```

The web interface provides a graphical conversation testing environment, supporting real-time viewing of order status and debugging information.

#### Method 2: Command-line Testing (Recommended for learning)

```bash
# Run the complete ordering process demonstration
python main.py

# Or directly start the Agent service
python agent.py
# The service will listen on http://0.0.0.0:8000
```

## AgentKit Deployment

### Prerequisites

**Important Note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the case can be executed normally.

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get AK/SK

### AgentKit Cloud Deployment

```bash
cd python/02-use-cases/08_restaurant_ordering

# Configure deployment parameters
agentkit config

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'Hello, I'd like something spicy.'

# Or use client.py to connect to the cloud service
# You need to edit client.py, change the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
# Modify client.py as needed, line 56, the content of the request
uv run client.py
```

## Example Prompts

### Basic Ordering Process

**Single Item Ordering**:

```text
User: Hello, I'd like something spicy.
Agent: I recommend Kung Pao Chicken, it's a classic spicy dish.
      [Calls add_to_order("Kung Pao Chicken")]
      Kung Pao Chicken has been added for you.

User: And a serving of dumplings.
Agent: Okay!
      [Calls add_to_order("Dumplings")]
      Dumplings have been added for you.

User: I'm done ordering, check please.
Agent: [Calls summarize_order]
      Here is your order:
      - Kung Pao Chicken
      - Dumplings
```

### Parallel Tool Calls

**Ordering multiple dishes at once**:

```text
User: I want a Kung Pao Chicken and a serving of dumplings.
Agent: Okay!
      [Parallel call to add_to_order("Kung Pao Chicken")]
      [Parallel call to add_to_order("Dumplings")]
      Kung Pao Chicken and dumplings have been added for you.
```

### Off-menu Requests

**Special Dish Inquiry**:

```text
User: Do you have any dishes made with crab?
Agent: [Calls web_search to search for crab dish information]
      We don't have crab dishes on our menu, but I can ask the kitchen if they can make one for you.
      Would you like to order a special crab dish?

User: Sounds good, make one as you suggested.
Agent: [Calls add_to_order("Special Crab Dish")]
      A special crab dish has been added for you.
```

### Complete Conversation Flow

Running `main.py` shows the complete ordering demonstration:

```python
prompts = [
    "Hello, I'd like something spicy.",
    "Do you have any dishes made with crab?",
    "Sounds good, make one as you suggested.",
    "And another serving of Kung Pao Chicken.",
    "I'm done ordering, check please.",
]
```

Output:

```bash
[Plugin] Agent run count: 1
[Plugin] LLM request count: 1
** User says: Hello, I'd like something spicy.
** restaurant_ordering_agent: I recommend Kung Pao Chicken...

[Plugin] Agent run count: 2
[Plugin] LLM request count: 2
** User says: Do you have any dishes made with crab?
** restaurant_ordering_agent: Let me check...

...

** restaurant_ordering_agent: Here is your order:
- Kung Pao Chicken
- Special Crab Dish
- Kung Pao Chicken
```

## Effect Demonstration

## Technical Points

### 1. Asynchronous Tools and Parallel Calls

**Asynchronous Definition**:

```python
async def add_to_order(dish_name: str, tool_context: ToolContext = None) -> str:
    # Asynchronous functions support concurrent execution
    ...
```

**Parallel Call Prompt**:

```text
You can using parallel invocations to add multiple dishes to the order.
```

The Agent can initiate multiple tool calls simultaneously, significantly improving processing speed.

### 2. Advanced Context Management

**Event Compression (EventsCompactionConfig)**:

- Automatically compresses multi-turn conversation history into a summary
- Saves token count, reducing costs
- Configuration: Triggers compression every 3 calls

**Context Filtering (ContextFilterPlugin)**:

- Precisely controls the number of conversation turns to keep
- Configuration: Keep the last 8 rounds of conversation
- Ensures core context is not lost

### 3. State Management (ToolContext)

**Shared State**:

```python
# Add dish
tool_context.state["order"] = tool_context.state["order"] + [dish_name]

# Read order
order = tool_context.state.get("order", [])
```

`tool_context.state` persists between tool calls, enabling state sharing.

### 4. Custom Plugins

**Plugin Hooks**:

- `before_agent_callback`: Before the Agent runs
- `before_model_callback`: Before the LLM is called

**Observability**:

- Count Agent invocations
- Count LLM calls
- Monitor performance and costs

### 5. Semantic Understanding and Menu Matching

The Agent can:

- Understand vague requests ("spicy" → Kung Pao Chicken)
- Match menu items ("chicken dish" → Kung Pao Chicken)
- Handle synonyms and various expressions

### AgentKit Integration

```python
from agentkit.apps import AgentkitAgentServerApp

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)
```

## Next Steps

After completing the Restaurant Ordering example, you can explore more features:

1. **[A2A Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/a2a_simple/README.md)** - Learn the Agent-to-Agent communication protocol
2. **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents/README.md)** - Build more complex multi-agent collaboration systems
3. **[Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge/README.md)** - Use web search tools to plan trips
4. **[Video Generator](../../video_gen/README.md)** - Advanced video generation example

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [Google ADK Context Compaction](https://google.github.io/adk-docs/context/compaction/)

## Code License

This project is licensed under the Apache 2.0 License
