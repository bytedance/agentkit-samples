# Skills Sandbox - Build a Skills-Capable Agent with VeADK and AgentKit

Build a skills-capable Agent based on Volcengine VeADK and AgentKit.

## Overview

This example demonstrates how to create a skills-capable Agent in AgentKit.

## Key Features

- Skill loading methods: load local skills, load from the AgentKit platform Skills Center, and load from TOS.
- Skill execution methods: execute skills in the runtime, Skill Sandbox, or AIO (All in One) Sandbox.
- Upload skill task results to TOS.
- Support local debugging and cloud deployment.

## Agent Capabilities

```text
User message
    ↓
AgentKit Runtime
    ↓
Skills Sandbox
    ├── VeADK Agent (conversation engine)
    ├── ShortTermMemory (session memory)
    └── Volcengine Ark model (LLM)
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/bytedance/agentkit-samples/blob/main/python/01-tutorials/04-agentkit-tools/skills_sandbox/veadk-1.x.x/agent.py) - Main application that defines the Agent and memory component |
| **Test Client** | [client.py](https://github.com/bytedance/agentkit-samples/blob/main/python/01-tutorials/04-agentkit-tools/skills_sandbox/veadk-1.x.x/client.py) - SSE streaming invocation client |
| **Project Configuration** | [pyproject.toml](https://github.com/bytedance/agentkit-samples/blob/main/python/01-tutorials/04-agentkit-tools/skills_sandbox/veadk-1.x.x/pyproject.toml) - Dependency management with uv |
| **AgentKit Configuration** | agentkit.yaml - Cloud deployment configuration file |
| **Short-Term Memory** | Stores session context using a local backend |

## Directory Structure

```bash
skills_sandbox/veadk-1.x.x/
├── agent.py           # Agent runs a skills task
├── client.py          # Test client (SSE streaming invocation)
├── requirements.txt   # Python dependency list (must be specified during AgentKit deployment)
├── pyproject.toml     # Project configuration (uv dependency management)
├── agentkit.yaml      # AgentKit deployment configuration (automatically generated after running agentkit config)
├── Dockerfile         # Docker image build file (automatically generated after running agentkit config)
└── README.md          # Project documentation
```

## Run Locally

### Prerequisites

**1. Enable the Volcengine Ark model service:**

- Visit the [Volcengine Ark console](https://exp.volcengine.com/ark?mode=chat).
- Enable the model service.

**2. Obtain Volcengine access credentials:**

- Refer to the [user guide](https://www.volcengine.com/docs/6291/65568?lang=en) to obtain an AK/SK.

### Install Dependencies

#### 1. Install the uv package manager

```bash
# macOS / Linux (official installation script)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use Homebrew (macOS)
brew install uv
```

#### 2. Initialize project dependencies

```bash
# Enter the project directory
cd python/01-tutorials/04-agentkit-tools/skills_sandbox/veadk-1.x.x
```

You can install this project's dependencies with `pip`:

```bash
pip install -r requirements.txt
```

Or install them with `uv`:

```bash
# If you do not have a `uv` virtual environment, create one first
uv venv --python 3.12

# Manage dependencies with `pyproject.toml`
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Or manage dependencies with `requirements.txt`
uv pip install -r requirements.txt

# Activate the virtual environment
source .venv/bin/activate
```

### Prepare the Environment

```bash
# Configure the AgentKit tool ID (required for the AIO Sandbox)
export AGENTKIT_TOOL_ID=<Your_Tool_ID>

# Configure the Skill Space ID (optional, but recommended)
export SKILL_SPACE_ID=<Your_Skill_Space_ID>

# Volcengine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Debugging

```bash
# Enter the project directory
cd python/01-tutorials/04-agentkit-tools/skills_sandbox/veadk-1.x.x

# Start the VeADK web UI
veadk web --port 8080

# Open in your browser: http://127.0.0.1:8080
```

The web UI provides a graphical conversation testing environment and supports real-time inspection of message streams and debugging information.

You can also use the command line to test and debug `agent.py`.

```bash
cd python/01-tutorials/04-agentkit-tools/skills_sandbox/veadk-1.x.x

# Start the Agent service
uv run agent.py
# The service listens on http://0.0.0.0:8000

# Open a new terminal and run the test client
# Edit client.py first and change base_url on line 13 to http://0.0.0.0:8000
uv run client.py
```

## AgentKit Deployment

### Prerequisites

**Important:** Before running this example, visit the [AgentKit console authorization page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services and ensure the example can run properly.

**1. Enable the Volcengine Ark model service:**

- Visit the [Volcengine Ark console](https://exp.volcengine.com/ark?mode=chat).
- Enable the model service.

**2. Obtain Volcengine access credentials:**

- Refer to the [user guide](https://www.volcengine.com/docs/6291/65568?lang=en) to obtain an AK/SK.

**3. Create an AgentKit tool:**

- Select the tool type: Preset Tool -> Skill Sandbox.

![Create Skill Sandbox](assets/images/skill-sandbox-iam-role.jpeg)

**4. Set environment variables:**

```bash
# Volcengine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Deploy to AgentKit Cloud

```bash
cd python/01-tutorials/04-agentkit-tools/skills_sandbox/veadk-1.x.x

# Configure deployment parameters
# Optional: if you do not add --runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} in agentkit config,
# you can go to AgentKit Console -> Agent Runtime -> Key Components, select Sandbox Tool, and publish it.
agentkit config \
--agent_name agent_skills \
--entry_point 'agent.py' \
--runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} \
--runtime_envs SKILL_SPACE_ID={{your_skill_space_id}} \
--launch_type cloud

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'Please run the following workflow: 1. Write a PDF-processing skill that supports loading PDFs, editing PDFs, and extracting text from PDFs; 2. Register the completed skill to the skill space.'

# Or use client.py to connect to the cloud service
# Edit client.py first and change base_url and api_key on lines 13 and 14 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
uv run client.py
```

## Built-in Skills

- Remember to replace `{YOUR_TOS_BUCKET_NAME}`. This is the TOS bucket that AgentKit creates for users by default, in the format `agentkit-platform-{your_account_id}`. If this TOS bucket does not exist, you need to create it yourself.

| Skill | Description | Example Prompt |
| ------ | --- | --------- |
| tos-file-access | Upload files or directories to Volcengine TOS and download files from URLs. Use this skill in the following cases: (1) upload files or directories generated by the Agent, such as videos, images, reports, or output folders, to TOS for sharing; (2) download files from URLs before the Agent processes them. | Please run the following workflow: 1. Use `tos-file-access` to download a `topk_benchmark.cpp` code file from `https://agentkit-skills.tos-cn-beijing.volces.com/upload/topk_benchmark.cpp`. 2. Use `code-optimization` to improve this code by implementing the `my_topk_inplace` function. The performance must be excellent and better than the standard-library implementation in the code. 3. Use `tos-file-access` to upload the final output directory, including the final code and report, to the bucket `{YOUR_TOS_BUCKET_NAME}`. |
| code-optimization | Optimize code performance through iterative improvement, up to 2 rounds. Benchmark execution time and memory usage, compare them with the baseline implementation, and generate a detailed optimization report. Supports C++, Python, Java, Rust, and other languages. | See the prompt in the previous `tos-file-access` row. |
| veadk-python | Implement a runnable Agent based on the VeADK framework. | Please run the following workflow: 1. Use the `veadk-python` skill to write a VeADK Agent that can reply when asked "hello". 2. Write the completed code to a new local code file, then use the `tos-file-access` skill to upload this code file to the bucket `{YOUR_TOS_BUCKET_NAME}`, and finally send me the uploaded code file link. |
| docx | See [docx](https://github.com/anthropics/skills/tree/main/skills/docx) for details. | |
| internal-comms | See [internal-comms](https://github.com/anthropics/skills/tree/main/skills/internal-comms) for details. | |
| pdf | See [pdf](https://github.com/anthropics/skills/tree/main/skills/pdf) for details. | |
| pptx | See [pptx](https://github.com/anthropics/skills/tree/main/skills/pptx) for details. | |
| skill-creator | See [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) for details. | |
| xlsx | See [xlsx](https://github.com/anthropics/skills/tree/main/skills/xlsx) for details. | |

## Example Prompts

## Results

| Example Prompt | Screenshot |
| -------- | ------- |
| Please run the following workflow: 1. Write a PDF-processing skill that supports loading PDFs, editing PDFs, and extracting text from PDFs; 2. Register the completed skill to the skill space. | ![Generated skill screenshot](assets/images/create.jpeg) |
| Please run the following workflow: 1. Use the `veadk-python` skill to write a VeADK Agent that can reply when asked 'hello'. 2. Execute the code to make sure it works; 3. Send me the verified code. | ![veadk skill screenshot](assets/images/veadk-skill.png) |
| Use the `internal-comms` skill to help me write a 3P communication document notifying the 3P team about project progress updates. For the product team, mainly cover issues from the past week and plans for the coming week. Specifically, include the issues encountered by the product team: (1) GPU + model inference framework performance is lower than the open-source version, such as higher latency and lower throughput; (2) GPU inference tools have poor usability, and explain how these issues were resolved. For the plan, describe next year's roadmap for GPU product features and performance optimization: (1) strengthen GPU infrastructure support for image and video generation models; (2) improve the usability of the GPU inference toolchain. You may organize the remaining content as appropriate. | ![internal-comms skill screenshot](assets/images/internal-comms-skill.jpeg) |
| Please run the following workflow: 1. Use the `canvas-design` skill to create an artistic drawing based on geometric shapes. 2. Use the `tos-file-access` skill to upload the output to the bucket `{YOUR_TOS_BUCKET_NAME}`. | ![canvas-design skill screenshot](assets/images/canvas-design-skill.jpeg) |
| I need a high-protein vegan meal plan for 2 people, with a muscle-gain goal. The weekly budget is 350 RMB. I prefer quick dishes that can be made within 30 minutes. I do not like mushrooms. Use the `healthy-meal-planner` skill to create a one-week meal plan for me. | ![healthy-meal-planner skill screenshot](assets/images/health-meal-planner-skill.jpeg) |
| Please run the following workflow: 1. I need a high-protein vegan meal plan for 2 people, with a muscle-gain goal. The weekly budget is 350 RMB. I prefer quick dishes that can be made within 30 minutes. I do not like mushrooms. Use the `healthy-meal-planner` skill to create a one-week meal plan for me. 2. Write the completed meal plan to `recipe.md`, then use the `tos-file-access` skill to upload this file to the bucket `{YOUR_TOS_BUCKET_NAME}`, and finally send me the uploaded file link. | ![healthy-meal-planner skill upload result to TOS screenshot](assets/images/health-meal-planner-skill-tos.png) |

## FAQ

None.

## References

- [VeADK official documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit development guide](https://volcengine.github.io/agentkit-sdk-python/)
