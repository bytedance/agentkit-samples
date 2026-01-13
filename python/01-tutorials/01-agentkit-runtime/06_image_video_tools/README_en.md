# Image and Video Tools - Image and Video Generation Agent

A creative content generation example based on Volcano Engine VeADK and multimedia generation tools, demonstrating how to generate image and video content through multi-agent collaboration.

## Overview

This example demonstrates how to use VeADK to build a multi-agent system to generate images or videos based on text descriptions.

## Core Functions

- Multi-agent architecture: The main Agent coordinates multiple sub-Agents
- Image generation: Convert text descriptions into images
- Video generation: Generate videos based on images or text
- Content search: Use Web search to enhance creative capabilities

## Agent Capabilities

```text
User Input (text description)
    ↓
Main Agent (eposide_generator)
    ├── Image Generator (image generation sub-Agent)
    │   └── image_generate tool
    │
    ├── Video Generator (video generation sub-Agent)
    │   └── video_generate tool
    │
    └── Web Search (content search)
        └── web_search tool
```

### Core Components

| Component | Description |
| - | - |
| **Main Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L37-L43) - eposide_generator, coordinates sub-Agents |
| **Image Generation Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L30-L35) - image_generator, generates images |
| **Video Generation Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L23-L28) - video_generator, generates videos |
| **Built-in Tools** | `image_generate`, `video_generate`, `web_search` |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/pyproject.toml) - dependency management (uv tool) |

### Code Features

**Sub-Agent Definition** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L23-L35)):

```python
video_generator = Agent(
    name="video_generator",
    description="Video Generation Agent",
    instruction="You are an atomic Agent with video generation capabilities. After each execution, consider returning to the main Agent.",
    tools=[video_generate],
)

image_generator = Agent(
    name="image_generator",
    description="Image Generation Agent",
    instruction="You are an atomic Agent with image generation capabilities. After each execution, consider returning to the main Agent.",
    tools=[image_generate],
)
```

**Main Agent Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L37-L43)):

```python
root_agent = Agent(
    name="eposide_generator",
    description="Call sub-Agents to generate images or videos",
    instruction="""You can generate videos or images based on a short piece of text entered by the user""",
    sub_agents=[image_generator, video_generator],
    tools=[web_search],
)
```

**Usage Example** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/06_image_video_tools/agent.py#L47-L67)):

```python
async def main(prompts: list[str]):
    session_id = uuid.uuid4().hex
    for prompt in prompts:
        response = await runner.run(
            messages=prompt,
            session_id=session_id,
        )
        print(response)

# Example prompts
asyncio.run(main([
    "Please generate the first frame image of the ancient Chinese prose 'Luoxia yu guwu qifei, qiushui gong changtian yise' (Rosy clouds and solitary ducks fly together, autumn water merges with the vast sky).",
    "Generate a video from the first frame image just now.",
]))
```

## Directory Structure Description

```bash
06_image_video_tools/
├── agent.py                    # Agent application entry point
├── requirements.txt            # Python dependency list
├── pyproject.toml              # Project configuration (uv dependency management)
└── README.md                   # Project description document
```

## Local Running

### Prerequisites

**Important note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure that the case can be executed normally.

**1. Activate Volcano Ark Model Service:**

- Visit [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Activate Multimedia Generation Service:**

- Ensure that image generation and video generation services have been activated
- Refer to [Video Generation Documentation](https://www.volcengine.com/docs/6791/1106485)

**3. Obtain Volcano Engine Access Credentials:**

- Refer to [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to obtain AK/SK

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
cd python/01-tutorials/01-agentkit-runtime/06_image_video_tools
```

Use the `uv` tool to install the project dependencies:

```bash
# If there is no `uv` virtual environment, you can use the command to create a virtual environment first
uv venv --python 3.12

# Use `pyproject.toml` to manage dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

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
```

### Debugging Methods

#### Method 1: Use the VeADK Web debugging interface

```bash
# Go to the parent directory
cd python/01-tutorials/01-agentkit-runtime

# Start the VeADK Web interface
veadk web

# Visit in the browser: http://127.0.0.1:8000
```

The Web interface provides a graphical dialogue testing environment, supporting real-time viewing of generated images and videos.

#### Method 2: Command line testing (recommended for learning)

```bash
# Run the example script
uv run agent.py

# The script will execute two tasks in sequence:
# 1. Generate an image of the ancient Chinese prose
# 2. Generate a video based on the image
```

## AgentKit Deployment

### Prerequisites

**Important note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure that the case can be executed normally.

**1. Activate Volcano Ark Model Service:**

- Visit [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service

**2. Obtain Volcano Engine Access Credentials:**

- Refer to [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to obtain AK/SK

### AgentKit Cloud Deployment

```bash
cd python/01-tutorials/01-agentkit-runtime/06_image_video_tools

# Configure deployment parameters
agentkit config

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'Please generate the first frame image of the ancient Chinese prose "Luoxia yu guwu qifei, qiushui gong changtian yise"'

# Or use client.py to connect to the cloud service
# You need to edit client.py and change the base_url and api_key in lines 14 and 15 to the runtime_endpoint and runtime_apikey fields generated in agentkit.yaml
# Modify client.py as needed, line 56, the content of the request
uv run client.py
```

## Example Prompts

### Image Generation

**Generate an image based on a text description**:

```text
User: Please generate the first frame image of the ancient Chinese prose "Luoxia yu guwu qifei, qiushui gong changtian yise"
Agent: I will generate an image of this ancient Chinese scene for you...
      [Call image_generator → image_generate tool]
      The image has been generated, showing the artistic conception of rosy clouds, solitary ducks, and autumn water merging with the vast sky.
```

### Video Generation

**Generate a video based on an image**:

```text
User: Generate a video from the first frame image just now.
Agent: I will generate a video based on the image just now...
      [Call video_generator → video_generate tool]
      The video has been generated, presenting you with a dynamic artistic conception of ancient Chinese prose.
```

### Creative Scenes

**Cosmic science fiction scene**:

```text
User: Generate a scene picture of a spaceship sailing in interstellar space
Agent: [Generate a science fiction style spaceship picture]

User: Make this picture into a video
Agent: [Generate a dynamic video of the spaceship sailing]
```

### Enhanced with Search

**Generate content based on search results**:

```text
User: Search for the characteristics of Mount Fuji, and then generate a picture of Mount Fuji
Agent: [Call web_search to search for information about Mount Fuji]
      [Generate a picture of Mount Fuji based on the search results by calling image_generate]
      A picture of Mount Fuji has been generated for you, showing features such as snow-capped mountains and cherry blossoms.
```

## Effect Display

## Technical Points

### Multi-agent Architecture

- **Main Agent**: Responsible for understanding user intent and coordinating sub-Agents
- **Sub-Agent**: Focus on a single function (image or video generation)
- **Atomic design**: Each sub-Agent returns to the main Agent after completing its task
- **Tool isolation**: Each sub-Agent only has specific tools

### Built-in Tools

**Image Generation Tool**:

```python
from veadk.tools.builtin_tools.image_generate import image_generate
```

**Video Generation Tool**:

```python
from veadk.tools.builtin_tools.video_generate import video_generate
```

**Web Search Tool**:

```python
from veadk.tools.builtin_tools.web_search import web_search
```

### Multi-turn Dialogue Context

- Use `session_id` to maintain session context
- Support continuous generation (image first, then video)
- The Agent can understand contextual references such as "the image just now"

### Workflow

1. **User input**: Provide a text description
2. **Main Agent understanding**: Analyze whether it is an image or video request
3. **Delegate to sub-Agent**: Call the corresponding sub-Agent
4. **Tool execution**: The sub-Agent calls the generation tool
5. **Result return**: The generated image/video is returned to the user

## Frequently Asked Questions

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [Video Generation Tool Documentation](https://volcengine.github.io/veadk-python/tools/builtin/#video-generate)

## Code License

This project follows the Apache 2.0 License
