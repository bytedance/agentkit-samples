# Image and Video Tools - Image and Video Generation Agent

A creative content generation example based on Volcano Engine VeADK and multimedia generation tools, demonstrating how to generate image and video content through Agent.

## Overview

This example demonstrates how to use VeADK to build a multi-agent system to generate images or videos based on text descriptions.

## Core Functions

- Single Agent architecture: Use a single Agent to coordinate all tools
- Image generation: Convert text descriptions into images
- Video generation: Generate videos based on images or text
- Content search: Use Web search to enhance creative capabilities

## Agent Capabilities

```text
User Input (text description)
    ↓
Main Agent (image_video_tools_agent)
    ├── web_search tool (search background information)
    ├── image_generate tool (generate images)
    └── video_generate tool (generate videos)
```

### Core Components

| Component | Description |
| - | - |
| **Main Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L38-L69) - image_video_tools_agent, responsible for understanding user intent and calling tools |
| **Built-in Tools** | `image_generate`, `video_generate`, `web_search` |
| **Service Framework** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L81-L89) - AgentkitAgentServerApp, provides HTTP service interface |
| **Client Test** | [client.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/client.py) - Test client, used to call deployed cloud service |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/pyproject.toml) - dependency management |

### Code Features

**Main Agent Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L38-L69)):

```python
root_agent = Agent(
    name="image_video_tools_agent",
    description="Call tools to generate images or videos",
    instruction="""
    You are an image and video generation assistant with image generation and video generation capabilities. There are three available tools:
    - web_search: Used to search for relevant information.
    - image_generate: Used to generate images.
    - video_generate: Used to generate videos.

    ### Workflow:

    1. When the user provides input, prepare relevant background information based on the user input:
       - If the user input is a story or plot, directly call the web_search tool;
       - If the user input is of other types (such as questions or requests), call the web_search tool first (up to 2 times) to find suitable information.
    2. Based on the prepared background information, call the image_generate tool to generate storyboard images. After generation, return them in Markdown image list format, for example:
        ```
        ![Storyboard Image 1](https://example.com/image1.png)
        ```
    3. Based on the user input, determine whether to call the video_generate tool to generate videos. When returning video URLs, use Markdown video link list format, for example:
        ```
        <video src="https://example.com/video1.mp4" width="640" controls>Storyboard Video 1</video>
        ```
    
    ### Notes:
    - In any input and output, any URLs involving images or videos, **absolutely prohibit any form of modification, truncation, stitching, or replacement**, must maintain 100% the completeness and accuracy of the original content.
    """,
    tools=[web_search, image_generate, video_generate],
)
```

**Service Startup** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L81-L89)):

```python
short_term_memory = ShortTermMemory(backend="local")

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
```

**Usage Example** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/3bc92248d02a71c3a75d737931ed96b796aafc10/python/01-tutorials/01-agentkit-runtime/image_video_tools/agent.py#L71-L79)):


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
    "Please generate the first frame image of the ancient Chinese prose 'Luoxia yu guwu qifei, qiushui gong changtian yise' (落霞与孤鹜齐飞，秋水共长天一色).",
    "Generate a video from the first frame image just now.",
]))
```

## Directory Structure Description

```bash
image_video_tools/
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
- Refer to [Video Generation Documentation](https://www.volcengine.com/docs/82379/1366799)

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
cd 01-tutorials/01-agentkit-runtime/image_video_tools

# Use uv to install dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Activate the virtual environment
source .venv/bin/activate
```

### Environment Preparation

```bash
# Volcano Ark model name
export MODEL_AGENT_NAME=deepseek-v3-2-251201

# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Start Service

#### Method 1: Run service directly (recommended)

```bash
# Start Agent service (default port 8000)
uv run agent.py

# After service starts, you can test it in the following ways:
# 1. Use client.py for testing
# 2. Use VeADK Web debugging interface
```

#### Method 2: Use VeADK Web debugging interface

```bash
# Go to the parent directory
cd python/01-tutorials/01-agentkit-runtime

# Start the VeADK Web interface
veadk web

# Visit in the browser: http://127.0.0.1:8000
```

The Web interface provides a graphical dialogue testing environment, supporting real-time viewing of generated images and videos.

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
cd python/01-tutorials/01-agentkit-runtime/image_video_tools

# Configure deployment parameters
agentkit config

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'Please generate the first frame image of the ancient Chinese prose "Luoxia yu guwu qifei, qiushui gong changtian yise"'
```

### Use Client for Testing

Edit [client.py](client.py#L14-L16), change `base_url` and `api_key` to the `runtime_endpoint` and `runtime_apikey` fields generated in `agentkit.yaml`:

```python
base_url = "http://<runtime_endpoint>"
api_key = "<runtime_apikey>"
```

Run client for testing:

```bash
uv run client.py
```

## Example Prompts

### Image Generation

**Generate an image based on a text description**:

```text
User: Please generate the first frame image of the ancient Chinese prose "Luoxia yu guwu qifei, qiushui gong changtian yise"
Agent: I will generate an image of this ancient Chinese scene for you...
      [Call web_search to search background information]
      [Call image_generate to generate image]
      The image has been generated, showing the artistic conception of rosy clouds, solitary ducks, and autumn water merging with the vast sky.
      ![Storyboard Image 1](https://example.com/image1.png)
```

### Video Generation

**Generate a video based on a text description**:

```text
User: Generate a video of a spaceship sailing in interstellar space
Agent: [Call web_search to search for relevant background]
      [Call video_generate to generate video]
      The video has been generated, presenting you with the scene of a spaceship sailing in interstellar space.
      <video src="https://example.com/video1.mp4" width="640" controls>Spaceship Sailing Video</video>
```

### Enhanced with Search

**Generate content based on search results**:

```text
User: Search for the characteristics of Mount Fuji, and then generate a picture of Mount Fuji
Agent: [Call web_search to search for information about Mount Fuji]
      [Based on search results, call image_generate to generate Mount Fuji picture]
      A picture of Mount Fuji has been generated for you, showing features such as snow-capped mountains and cherry blossoms.
```

## Effect Display

## Technical Points

### Single Agent Architecture

- **Main Agent**: Responsible for understanding user intent, directly calling all tools
- **Tool integration**: All tools (web_search, image_generate, video_generate) are integrated in the main Agent
- **Workflow**: Search background information → Generate images → Generate videos as needed

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
- Use `ShortTermMemory` to store conversation history
- The Agent can understand contextual references

### HTTP Service Interface

- Use `AgentkitAgentServerApp` to provide HTTP service
- Default port 8000
- Support SSE streaming response

### Workflow

1. **User input**: Provide a text description
2. **Agent understanding**: Analyze user intent, determine which tools to call
3. **Background search** (as needed): Call web_search to search for relevant information
4. **Image generation**: Call image_generate to generate images
5. **Video generation** (as needed): Call video_generate to generate videos
6. **Result return**: Return image/video links in Markdown format

## Frequently Asked Questions

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [Video Generation Tool Documentation](https://volcengine.github.io/veadk-python/tools/builtin/#video-generate)

## Code License

This project follows the Apache 2.0 License
