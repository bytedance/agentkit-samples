# Skills Sandbox - Build a Skills-Capable Agent with VeADK and AgentKit

Build a skills-capable Agent based on VeADK and BytePlus AgentKit.

## Overview

This example demonstrates how to create a skills-capable Agent in AgentKit.

## Differences from veadk_0_x_x

The `veadk_0_x_x` examples mainly use the legacy `Agent(skills=...)` wrapper to
load skills:

```python
agent = Agent(
    skills=[skill_space_id],
    tools=[execute_skills],
)
```

For local execution, they usually rely on `skills_mode="local"`:

```python
agent = Agent(
    skills=[skill_space_id],
    skills_mode="local",
)
```

`veadk_1_x_x` more commonly uses the ADK Toolset style for remote skills:

```python
registry = VeSkillRegistry(skill_source_id=skill_space_id)
skill_toolset = SkillToolset(registry=registry)

agent = Agent(
    tools=[skill_toolset],
)
```

Key differences:

| Dimension | veadk_0_x_x | veadk_1_x_x |
| --- | --- | --- |
| Skill loading | Mainly `Agent(skills=[...])` | Mainly `SkillToolset(registry=VeSkillRegistry(...))` |
| Local execution for remote registry skills | `skills_mode="local"` | Use `SkillToolset`; the legacy `skills_mode="local"` path is no longer recommended |
| Skills Sandbox execution | Runtime Agent mounts `execute_skills` | Supports both synchronous `execute_skills` and non-blocking `invoke_skill/poll_skill` flows |
| AIO/run_code execution | Not fully covered by the old examples | Loads remote skills with `SkillToolset` and uses `run_code` for AIO/script sandbox execution |
| A2A invocation | No standalone A2A invocation scripts | `advanced/a2a/` provides both direct sandbox invocation and runtime-Agent examples |
| Runtime Agent location | Runs locally in the example scripts | Current scripts also run the runtime Agent locally; the invoked sandbox is remote |

## A2A and Sandbox Support

With `veadk-python==1.1.9`, the following runtime Agent to sandbox flows are
supported:

| Scenario | Supported | Flow | Entry point |
| --- | --- | --- | --- |
| Skills Sandbox synchronous delegation | Yes | `runtime Agent (execute_skills) -> Skills Sandbox (VeADK Agent -> runtime)` | `advanced/a2a/runtime_to_skills_sandbox_execute.py` |
| Skills Sandbox non-blocking tasks | Yes | `runtime Agent (invoke_skill, poll_skill) -> Skills Sandbox (VeADK Agent -> runtime)` | `advanced/a2a/runtime_to_skills_sandbox_invoke_poll.py` |
| AIO Sandbox code execution | Yes | `runtime Agent (run_code) -> AIO/script Sandbox` | `advanced/a2a/runtime_to_aio_sandbox_run_code.py` |

In the Skills Sandbox synchronous delegation sample, the runtime Agent mounts
only `execute_skills`; it does not mount bash or code execution tools:

```python
agent = Agent(
    name="remote_skills_runtime_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
    instruction=ROOT_AGENT_INSTRUCTION,
    skills=[os.getenv("SKILL_SPACE_ID")],
    skills_mode="skills_sandbox",
    tools=[execute_skills],
)
```

The Skills Sandbox non-blocking task sample uses the non-blocking tools provided
by `veadk-python==1.1.9`. The tool names are singular: `invoke_skill` and
`poll_skill`.

```python
from google.adk.tools.skill_toolset import SkillToolset
from veadk.skills import VeSkillRegistry
from veadk.tools.builtin_tools.invoke_skill import invoke_skill
from veadk.tools.builtin_tools.poll_skill import poll_skill

skill_toolset = SkillToolset(
    registry=VeSkillRegistry(skill_source_id=os.getenv("SKILL_SPACE_ID")),
)

agent = Agent(
    name="skill_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[skill_toolset, invoke_skill, poll_skill] if skill_toolset else [],
)
```

In the AIO Sandbox code execution sample, the runtime Agent mounts
`SkillToolset` and `run_code`. Remote skills are loaded through
`SKILL_SPACE_ID`, and code or shell commands are delegated to the AIO/script
sandbox through `run_code`.

See `advanced/a2a/README.md` for complete command-line examples.

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
    └── BytePlus ModelArk model (LLM)
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

**1. Enable the BytePlus ModelArk service:**

- Visit the [BytePlus ModelArk console](https://console.byteplus.com/ark/region:ark+ap-southeast-1/overview).
- Enable the model service.

**2. Obtain BytePlus access credentials:**

- Create an AK/SK in the [BytePlus console](https://console.byteplus.com).

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

# Configure the AgentKit Skill Space ID (required; use the ID beginning with ss-)
export SKILL_SPACE_ID=<Your_Skill_Space_ID>

# BytePlus access credentials (required)
export BYTEPLUS_ACCESS_KEY=<Your Access Key>
export BYTEPLUS_SECRET_KEY=<Your Secret Key>
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_REGION=ap-southeast-1
```

`agent.py` reads the remote Skill Space from `SKILL_SPACE_ID`. Set it before starting the local service; otherwise, the remote Skill Registry cannot be initialized.

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

**Important:** Before running this example, authorize all dependent services in the [BytePlus AgentKit console](https://console.byteplus.com/agentkit).

**1. Enable the BytePlus ModelArk service:**

- Visit the [BytePlus ModelArk console](https://console.byteplus.com/ark/region:ark+ap-southeast-1/overview).
- Enable the model service.

**2. Obtain BytePlus access credentials:**

- Create an AK/SK in the [BytePlus console](https://console.byteplus.com).

**3. Create an AgentKit tool:**

- Select the tool type: Preset Tool -> Skill Sandbox.

![Create Skill Sandbox](assets/images/skill-sandbox-iam-role.jpeg)

**4. Set environment variables:**

```bash
# AgentKit Skill Space ID (required; use the ID beginning with ss-)
export SKILL_SPACE_ID=<Your_Skill_Space_ID>

# BytePlus access credentials (required)
export BYTEPLUS_ACCESS_KEY=<Your Access Key>
export BYTEPLUS_SECRET_KEY=<Your Secret Key>
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_REGION=ap-southeast-1
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

### Invoke a Sandbox directly over A2A

To create or reuse a Sandbox Session and invoke its A2A endpoint directly, see
the [A2A invocation guide](advanced/a2a/README_en.md).

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
