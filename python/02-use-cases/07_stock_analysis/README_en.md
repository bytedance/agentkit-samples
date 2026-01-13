# Stock Analysis Intelligent Assistant - Stock Analysis

## Overview

This is an intelligent assistant with stock analysis capabilities built based on the Volcano Engine AgentKit.

This assistant is for tutorial purposes only. The output content does not constitute investment advice. Please use or modify it reasonably according to the application scenario. If necessary, you can seek guidance from a professional investment advisor.

## Core Functions

- Function 1: Stock data analysis
- Function 2: Stock trend prediction
- Function 3: Stock investment advice

## Agent Capabilities

```text
User Message
    ↓
AgentKit Runtime
    ↓
Stock Analysis Agent
    ├── Web Search Tool (web_search)
    ├── Code Execution Tool (run_code)
```

## Directory Structure Description

```bash
07_stock_analysis/
├── agent.py           # Agent
├── client.py          # Test client (SSE streaming call)
├── requirements.txt   # Python dependency list (dependency file needs to be specified during agentkit deployment)
├── pyproject.toml     # Project configuration (uv dependency management)
├── agentkit.yaml      # AgentKit deployment configuration (will be automatically generated after running agentkit config)
├── Dockerfile         # Docker image build file (will be automatically generated after running agentkit config)
└── README.md          # Project description document
```

## Local Running

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to obtain AK/SK

**3. Activate `web_search` tool permissions:**

- To use the [`web_search` tool](https://www.volcengine.com/docs/85508/1650263), you need to activate and create a networked question-answering Agent with [corresponding permissions](https://www.volcengine.com/docs/85508/1544858) in advance.

**4. Create AgentKit Tool:**

- Tool type selection: Preset Tool -> AIO Sandbox

### Dependency Installation

#### 1. Install uv package manager

```bash
# macOS / Linux (official installation script)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use Homebrew (macOS)
brew install uv
```

#### 2. Initialize project dependencies

```bash
# Enter the project directory
cd python/02-use-cases/07_stock_analysis
```

You can use the `pip` tool to install the project dependencies:

```bash
pip install -r requirements.txt
```

Or use the `uv` tool to install the project dependencies:

```bash
# If there is no `uv` virtual environment, you can use the command to create a virtual environment first
uv venv --python 3.12

# Use `pyproject.toml` to manage dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Use `requirements.txt` to manage dependencies
uv pip install -r requirements.txt

# Activate the virtual environment
source .venv/bin/activate
```

### Environment Preparation

```bash
# Volcano Ark model name
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

export AGENTKIT_TOOL_ID=<Your Tool ID>
```

### Debugging Methods

#### Single-threaded operation: Use the VeADK Web debugging interface to debug agent.py

```bash
# Enter the 02-use-cases directory
cd agentkit-samples/02-use-cases

# Start the VeADK Web interface
veadk web --port 8080

# Visit in the browser: http://127.0.0.1:8080
```

The Web interface provides a graphical dialogue testing environment, supporting real-time viewing of message streams and debugging information.

In addition, you can also use the command line to test and debug agent.py.

```bash
cd python/02-use-cases/07_stock_analysis

# Start the Agent service
uv run agent.py
# The service will listen on http://0.0.0.0:8000

# Open a new terminal and run the test client
# You need to edit client.py and change the base_url and api_key in lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
uv run client.py
```

## AgentKit Deployment

### Prerequisites

**Important note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure that the case can be executed normally.

**1. Activate Volcano Ark Model Service:**

- Visit [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to obtain AK/SK

**3. Activate `web_search` tool permissions:**

- To use the [`web_search` tool](https://www.volcengine.com/docs/85508/1650263), you need to activate and create a networked question-answering Agent with [corresponding permissions](https://www.volcengine.com/docs/85508/1544858) in advance.

**4. Create AgentKit Tool:**

- Tool type selection: Preset Tool -> AIO Sandbox

**5. Set environment variables:**

```bash
# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### AgentKit Cloud Deployment

```bash
cd python/02-use-cases/07_stock_analysis

# Configure deployment parameters
# optional: If you do not add --runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} in agentkit config, you can select the Sandbox Tool in the AgentKit console's intelligent agent runtime, key components, and publish
agentkit config \
--agent_name stock_analysis \
--entry_point 'agent.py' \
--runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} \
--launch_type cloud

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'Help me search for the recent stock trend of CATL and give me a simple investment suggestion.'

# Or use client.py to connect to the cloud service
# You need to edit client.py and change the base_url and api_key in lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
uv run client.py
```

## Example Prompts

Here are some commonly used prompt examples:

- "Help me search for recent stock data of BYD and analyze the trend"
- "Help me search for the recent stock trend of CATL and give me a simple investment suggestion"

## Effect Display

| Example Prompt 1 | Example Prompt 2 |
| -------- | ------- |
| Help me search for recent stock data of BYD and analyze the trend. | Help me search for the recent stock trend of CATL and give me a simple investment suggestion |
| ![Example Prompt 1 Screenshot](assets/images/prompt1.jpeg) | ![Example Prompt 2 Screenshot](assets/images/prompt2.jpeg) |

## Frequently Asked Questions

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## Code License

This project follows the Apache 2.0 License
