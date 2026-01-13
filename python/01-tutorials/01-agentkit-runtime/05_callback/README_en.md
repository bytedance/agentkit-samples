# Callback - Agent Callback and Guardrail Demonstration

This is a callback mechanism example built based on Volcano Engine's VeADK and AgentKit, comprehensively demonstrating the callback functions and guardrail features at each stage of the Agent's lifecycle.

## Overview

This example demonstrates the complete Agent callback system in VeADK.

## Core Features

- **Six Major Callback Functions**: Covering the complete lifecycle of Agent execution
- **Guardrail Mechanism**: Input/output content moderation, PII information filtering
- **Tool Parameter Validation**: Parameter verification and preparation before execution
- **Result Post-processing**: Unified formatting and standardization of output
- **Full-link Logging**: Complete recording of the Agent's execution trace

## Agent Capabilities

```text
User Request
    ↓
before_agent_callback (Input guardrail, logging)
    ↓
AgentKit Runtime
    ↓
before_model_callback (Request preprocessing)
    ↓
LLM Model Call
    ↓
after_model_callback (Response post-processing, PII filtering)
    ↓
before_tool_callback (Parameter validation)
    ↓
Tool Execution (write_article)
    ↓
after_tool_callback (Result normalization)
    ↓
after_agent_callback (Cleanup, log summary)
    ↓
Return to User
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/agent.py) - The main Agent for configuring callbacks and guardrails |
| **Callback Functions** | [callbacks/](https://github.com/volcengine/agentkit-samples/tree/main/python/01-tutorials/01-agentkit-runtime/05_callback/callbacks) - Implementations of the six callback functions |
| **Tool Definition** | [tools/write_article.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/tools/write_article.py) - Article writing tool |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/pyproject.toml) - Dependency management |
| **Short-term Memory** | Local backend for storing session context |

### Code Features

**Agent Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/agent.py#L11-L22)):

```python
root_agent = Agent(
    name="ChineseContentModerator",
    description="A Chinese content moderation assistant demonstrating full-link callbacks and guardrail features.",
    instruction="You are a content assistant who can write articles according to user requirements. Make good use of the tools.",
    tools=[write_article],
    before_agent_callback=before_agent_callback,
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    after_agent_callback=after_agent_callback,
)
```

**Test Scenarios** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/agent.py#L37-L44)):

```python
# Scenario 1: Normal call, triggers tool and PII filtering
await runner.run(messages="Please help me write a 500-word article on 'the future of artificial intelligence'.")

# Scenario 2: Input contains sensitive words, intercepted by the guardrail
await runner.run(messages="Hello, I would like to know some information about zanghua.")

# Scenario 3: Tool parameter validation fails
await runner.run(messages="Write an article about 'space exploration' with -100 words.")
```

## Directory Structure

```bash
05_callback/
├── agent.py                    # Agent application entry point
├── callbacks/                  # Callback function implementations
│   ├── __init__.py
│   ├── before_agent_callback.py    # Before-agent callback
│   ├── after_agent_callback.py     # After-agent callback
│   ├── before_model_callback.py    # Before-model callback
│   ├── after_model_callback.py     # After-model callback
│   ├── before_tool_callback.py     # Before-tool callback
│   └── after_tool_callback.py      # After-tool callback
├── tools/                      # Tool definitions
│   ├── __init__.py
│   └── write_article.py        # Article writing tool
├── requirements.txt            # Python dependency list
├── pyproject.toml              # Project configuration (uv dependency management)
└── README.md                   # Project documentation
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
cd python/01-tutorials/01-agentkit-runtime/05_callback
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
cd python/01-tutorials/01-agentkit-runtime

# Start the VeADK Web interface
veadk web --port 8080

# Visit in your browser: http://127.0.0.1:8080
```

The web interface allows real-time viewing of callback execution order and log output.

#### Method 2: Command-line Testing

```bash
# Start the Agent service and run the test scenarios
uv run agent.py
```

**Execution Effect**:

```bash
==================== Scenario 1: Normal call, triggers tool and PII filtering ====================
[before_agent] Start processing request...
[before_model] Preparing to call the model...
[before_tool] Validating tool parameters...
[after_tool] Tool execution completed, normalizing result...
[after_model] PII information has been filtered...
[after_agent] Request processing completed

==================== Scenario 2: Input contains sensitive words, intercepted by the guardrail ====================
[before_agent] Sensitive words detected, request intercepted

==================== Scenario 3: Tool parameter validation fails ====================
[before_tool] Parameter validation failed: Word count must be a positive number
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
cd python/01-tutorials/01-agentkit-runtime/05_callback

# Configure deployment parameters
agentkit config

# Start the cloud service
agentkit launch

# Test the callback feature
agentkit invoke 'Please help me write a 500-word article on the future of artificial intelligence'

# Test the guardrail feature
agentkit invoke 'Hello, I would like to know some information about zanghua'

# Or use client.py to connect to the cloud service
# You need to edit client.py, change the base_url and api_key on lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
# Modify client.py as needed, line 56, the content of the request
uv run client.py
```

## Example Prompts

## Effect Demonstration

## Detailed Explanation of Callback Functions

### 1. before_agent_callback

**Function**: Pre-processing before the Agent starts running

**Typical Uses**:

- Input guardrail checks (sensitive word filtering)
- Initialize context variables
- Log the start of a request
- Request rate limiting and authentication

**Example** ([callbacks/before_agent_callback.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/callbacks/before_agent_callback.py)):

```python
def before_agent_callback(agent, callback_context):
    # Sensitive word check
    if contains_sensitive_words(callback_context.input):
        callback_context.reject("Sensitive content detected")
        return

    # Log
    logger.info(f"Start processing request: {callback_context.session_id}")
```

### 2. before_model_callback

**Function**: Request pre-processing before calling the LLM

**Typical Uses**:

- Modify the system prompt
- Supplement metadata and context
- Adjust parameters (temperature, max_tokens, etc.)
- Pre-process request content

**Example** ([callbacks/before_model_callback.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/callbacks/before_model_callback.py)):

```python
def before_model_callback(callback_context, llm_request):
    # Dynamically adjust the system instruction
    llm_request.system_instruction += "\nPlease ensure the reply is professional and friendly."

    # Adjust generation parameters
    llm_request.temperature = 0.7
    llm_request.max_tokens = 2000
```

### 3. after_model_callback

**Function**: Content post-processing after the LLM responds

**Typical Uses**:

- Format output content
- PII (Personally Identifiable Information) filtering
- Extract structured information
- Content moderation and rewriting

**Example** ([callbacks/after_model_callback.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/callbacks/after_model_callback.py)):

```python
def after_model_callback(callback_context, llm_response):
    # PII information filtering
    llm_response.content = filter_pii(llm_response.content)

    # Format output
    llm_response.content = format_markdown(llm_response.content)
```

### 4. before_tool_callback

**Function**: Parameter validation and preparation before tool execution

**Typical Uses**:

- Parameter type conversion and validation
- Default value filling
- Permission checks
- Lightweight parameter pre-processing

**Example** ([callbacks/before_tool_callback.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/callbacks/before_tool_callback.py)):

```python
def before_tool_callback(tool_context):
    # Parameter validation
    if tool_context.tool_name == "write_article":
        word_count = tool_context.parameters.get("word_count")
        if word_count and word_count < 0:
            raise ValueError("Word count must be a positive number")

    # Default value filling
    tool_context.parameters.setdefault("language", "zh-CN")
```

### 5. after_tool_callback

**Function**: Result processing after tool execution

**Typical Uses**:

- Normalize result format
- Append auxiliary information
- Persist results to storage
- Error handling and retries

**Example** ([callbacks/after_tool_callback.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/callbacks/after_tool_callback.py)):

```python
def after_tool_callback(tool_context, tool_result):
    # Normalize output format
    if tool_context.tool_name == "write_article":
        tool_result = {
            "content": tool_result,
            "word_count": len(tool_result),
            "timestamp": datetime.now().isoformat()
        }

    # Save to database
    save_to_database(tool_result)

    return tool_result
```

### 6. after_agent_callback

**Function**: Cleanup work after the Agent finishes execution

**Typical Uses**:

- Summarize execution logs
- Clean up temporary resources
- Generate execution reports
- Performance metric statistics

**Example** ([callbacks/after_agent_callback.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/05_callback/callbacks/after_agent_callback.py)):

```python
def after_agent_callback(agent, callback_context, result):
    # Summarize logs
    logger.info(f"Request completed: session_id={callback_context.session_id}")
    logger.info(f"Execution duration: {callback_context.duration}ms")
    logger.info(f"Number of tools called: {callback_context.tool_count}")

    # Clean up resources
    cleanup_temp_files(callback_context.session_id)
```

## Technical Points

### Callback Execution Order

```text
1. before_agent_callback      → Check input, initialize
2. before_model_callback       → Prepare model request
3. [LLM Call]                 → Model generates response
4. after_model_callback        → Process model output
5. before_tool_callback        → Validate tool parameters
6. [Tool Execution]                → Execute the specific tool
7. after_tool_callback         → Normalize tool result
8. [Loop 2-7 until completion]
9. after_agent_callback        → Final cleanup
```

### Guardrail Mechanism

**Input Guardrail**:

- Sensitive word detection and interception
- Malicious request identification
- Content security moderation

**Output Guardrail**:

- PII information filtering (ID cards, phone numbers, emails, etc.)
- Harmful content filtering
- Format normalization

### Use Cases

| Scenario | Callback Used | Purpose |
| - | - | - |
| **Content Moderation** | before_agent, after_model | Filter sensitive and harmful content |
| **Parameter Validation** | before_tool | Ensure tool parameters are valid |
| **Logging** | All callbacks | Trace the complete execution path |
| **Performance Monitoring** | before_agent, after_agent | Track response time |
| **Result Normalization** | after_tool, after_model | Unify output format |

## Extension Directions

### 1. Enhance Guardrail Functionality

- **Multi-level Moderation**: Integrate with third-party content moderation APIs
- **Custom Rules**: Configurable sensitive word lists
- **Risk Scoring**: Assess the risk of requests

### 2. Advanced Logging

- **Distributed Tracing**: Integrate with OpenTelemetry
- **Visual Monitoring**: Integrate with Grafana/Prometheus
- **Audit Logging**: Compliance audit records

### 3. Intelligent Optimization

- **Adaptive Parameters**: Adjust model parameters based on historical performance
- **A/B Testing**: Compare the effects of different strategies
- **Anomaly Detection**: Automatically identify abnormal requests

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## Code License

This project is licensed under the Apache 2.0 License
