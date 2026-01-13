# Video Generation Agent - Video Story Generator

This is a "Fable Storybook Video Generation" Agent based on Volcano Engine AgentKit. It will, based on the user-inputted fable storyline:

- Generate four cartoon-style storyboard illustrations
- Generate three transitional video segments with adjacent storyboards as the start and end frames
- Stitch the three video segments sequentially into a complete film using a local MCP tool
- Upload the finished film to Volcano Engine TOS and return an accessible signed URL

## Overview

## Core Features

This use case demonstrates how to build a production-level video generation system with the following capabilities:

- **Intelligent Story Assistant**: Based on the story or plot provided by the user, it understands and refines the storyline, combines it with background information retrieval, splits the story into three scenes, and rewrites the story description.
- **Storyboard Generation**: Based on the story description, it uses the large model's text-to-image capability to generate storyboard images.
- **Video Generation**: Based on the storyboard images, it pairs them sequentially according to the three scenes and uses the large model to generate three storyboard videos.
- **Product Hosting**: Downloads the storyboard videos locally, uses a local MCP tool to stitch them into a complete story video, and uploads the merged video to TOS object storage, generating an accessible preview link.
- **Observability**: Integrates OpenTelemetry tracing and APMPlus monitoring.

The system architecture is as follows:

![Video Generation Agent with AgentKit Runtime](img/archtecture_video_gen.jpg)

```text
User Request
    ↓
AgentKit Runtime
    ↓
Video Story Generator
    ├── Image Generation Tool (Visual AI)
    ├── Video Generation Tool (Visual AI)
    ├── File Download Tool (Batch Download)
    ├── Video Stitching Tool (MCP)
    └── TOS Upload Tool (Storage & Sharing)
```

Key features include:

- **Intelligent Storyboard Generation**: Automatically decomposes the narrative into 4 visual keyframes, maintaining style consistency and character continuity.
- **Seamless Video Transitions**: Uses advanced visual AI models to generate smooth transitional videos between frames.
- **Local MCP Tool Integration**: Utilizes the Model Context Protocol for efficient local video processing without cloud dependencies.
- **Automatic Upload & Sharing**: Uploads the completed video to TOS and generates a time-limited signed URL for secure sharing.
- **Iterative Optimization**: Maintains conversation context, allowing users to request adjustments to style, pacing, or content.

## Agent Capabilities

| Component | Description |
| --- | --- |
| **Agent Service** | [`agent.py`](agent.py) - Main application, includes MCP tool registration |
| **Agent Configuration** | [`agent.yaml`](agent.yaml) - Model settings, system instructions, and tool list |
| **Custom Tools** | [`tool/`](tool/) - File download and TOS upload utility tools |
| **MCP Integration** | `@pickstar-2002/video-clip-mcp` - Local video stitching service |
| **Short-term Memory** | Session context maintenance to preserve conversational continuity |

## Quick Start

### Prerequisites

#### Node.js Environment

- Install Node.js 18+ and npm ([Node.js Installation](https://nodejs.org/en))
- Ensure the `npx` command is available in the terminal
- Required for running the MCP video stitching tool

#### Volcano Engine Access Credentials

1. Log in to the [Volcano Engine Console](https://console.volcengine.com)
2. Go to "Access Control" → "Users" -> Create a new user or search for an existing username -> Click the username to enter "User Details" -> Go to "Keys" -> Create a new key or copy an existing AK/SK
    - As shown in the figure below
        ![Volcengine AK/SK Management](../img/volcengine_aksk.jpg)
3. Configure access permissions for the services that AgentKit depends on for the user:
    - On the "User Details" page -> Go to "Permissions" -> Click "Add Permission", and grant the following policies to the user
    - `AgentKitFullAccess` (AgentKit full access)
    - `APMPlusServerFullAccess` (APMPlus full access)
4. Obtain the Volcano Ark model Agent API Key for the user
    - Search for the "Volcano Ark" product and click to enter the console
    - Go to "API Key Management" -> Create or copy an existing API Key
    - As shown in the figure below
        ![Ark API Key Management](../img/ark_api_key_management.jpg)
5. Activate the model's pre-built inference access point
    - Search for the "Volcano Ark" product and click to enter the console
    - Go to "Activation Management" -> "Language Models" -> Find the corresponding model -> Click "Activate Service"
    - Activate the following models used in this case
        - root_agent model: `deepseek-v3-1-terminus`
        - Image generation model: `doubao-seedream-4-0-250828`
        - Video generation model: `doubao-seedance-1-0-pro-250528`
    - As shown in the figure below
        ![Ark Model Service Management](../img/ark_model_service_management.jpg)

### Install Dependencies

*It is recommended to use the uv tool to build the project*

```bash
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

cd python/02-use-cases/03_video_gen

# create virtual environment
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

**Note:** The MCP video tool (`@pickstar-2002/video-clip-mcp`) will be automatically started via `npx` when the agent is running. No manual installation is required.

### Configure Environment Variables

Set the following environment variables:

```bash
export VOLCENGINE_ACCESS_KEY={your_ak}
export VOLCENGINE_SECRET_KEY={your_sk}
export DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}
export MODEL_AGENT_API_KEY={{your_model_agent_api_key}} # Get from Volcano Ark, required for local debugging

# Optional: Specify download directory (defaults to project root)
export DOWNLOAD_DIR=/tmp
```

**TOS Bucket Configuration:**

- **Default bucket**: `agentkit-platform-{{your_account_id}}`
  - Where `{{your_account_id}}` needs to be replaced with your Volcano Engine account ID
  - Example: `DATABASE_TOS_BUCKET=agentkit-platform-12345678901234567890`
- **If you need to customize, you can modify the `bucket_name` parameter in [`tool/tos_upload.py`](tool/tos_upload.py) or pass it in during the tool call.**

## Local Execution

### Method 1: Direct API Call

Start the agent service:

```bash
uv run agent.py
# The service listens on 0.0.0.0:8000 by default
```

#### Step 1: Get the Application Name

The agent name is consistent with the `name` field in [`agent.yaml`](agent.yaml), which is `storybook_illustrator`.

```bash
curl --location 'http://localhost:8000/list-apps'
```

#### Step 2: Create a Session

```bash
curl --location --request POST 'http://localhost:8000/apps/storybook_illustrator/users/u_123/sessions/s_123' \
--header 'Content-Type: application/json' \
--data ''
```

#### Step 3: Send a Message

```bash
curl --location 'http://localhost:8000/run_sse' \
--header 'Content-Type: application/json' \
--data '{
    "appName": "storybook_illustrator",
    "userId": "u_123",
    "sessionId": "s_123",
    "newMessage": {
        "role": "user",
        "parts": [{
            "text": "Please generate a storybook video based on the fable 《The Fox and the Tiger》"
        }]
    },
    "streaming": true
}'
```

### Method 2: Use veadk web

Use `veadk web` for local debugging:

> `veadk web` is a web service based on FastAPI for debugging Agent applications. When you run this command, it starts a web server that loads and runs your agentkit agent code, while also providing a chat interface where you can interact with the agent. In the sidebar or a specific panel of the interface, you can view the details of the agent's execution, including the Thought Process, Tool calls, and model input/output.

```bash
# 1. Go to the parent directory
cd 02-use-cases

# 2. Start the veadk web interface
veadk web
```

Visit `http://localhost:8000` in your browser, select the `03_video_gen` agent, enter a prompt, and click "Send".

### Example Prompts

- **Chinese Idioms**: "A live-action version of Houyi shooting the suns, Chang'e flying to the moon, and Wu Gang chopping the tree"
- **Classic Stories**: "A storybook of The Foolish Old Man Who Removed the Mountains and Jingwei Filling the Sea"
- **Wuxia Novels**: "A live-action video story of The Legend of the Condor Heroes"
- **Xuanhuan Novels**: "Han Li forming his Nascent Soul in A Record of a Mortal's Journey to Immortality"
- **3D Animation**: "The great battle in the Void Sky Palace from A Record of a Mortal's Journey to Immortality, in 3D animation style"

**Expected Behavior:**

1. Generate 4 illustration storyboard frames
2. Create 3 transitional video segments between consecutive frames
3. Start the local MCP tool to stitch the videos
4. Upload the final video to TOS
5. Return a signed URL for viewing

## AgentKit Deployment

### Deploy to Volcano Engine AgentKit Runtime

Step 1: Enter the project directory

```bash
cd python/02-use-cases/03_video_gen
```

Step 2: Configure AgentKit**

```bash
agentkit config \
--agent_name storybook_illustrator \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}} \
--launch_type cloud
```

Modify the `agentkit.yaml` deployment configuration

> Purpose: After modification, it will pre-install video-clip-mcp during the image build phase to accelerate runtime startup.

```bash
# linux os command
sed -i 's/docker_build: {}/docker_build:\n  build_script: "scripts\/setup.sh"/' agentkit.yaml

# mac os command
sed -i '' 's/docker_build: {}/docker_build:/' agentkit.yaml && sed -i '' '/docker_build:/a\
  build_script: "scripts\/setup.sh"' agentkit.yaml
```

Step 4: Deploy to the runtime

```bash
agentkit launch
```

### Test the Deployed Agent

After successful deployment:

1. Visit the [Volcano Engine AgentKit Console](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/runtime)
2. Click **Runtime** to view the deployed agent `storybook_illustrator`
3. Get the public access domain name (e.g., `https://xxxxx.apigateway-cn-beijing.volceapi.com`) and API Key

#### **Debug based on page chatui**

The agent list page of Agentkit provides a debugging entry point. After clicking it, you can debug the agent's functions in a visually UI-based manner.

![img](./img/agent-test-run-01.png)

![img](./img/agent-test-run-02.png)

#### Debug based on command line

You can directly use agentkit invoke to initiate debugging of the current agent. The command is as follows:

```bash
agentkit invoke '{"prompt": "Draw a story of a panda's adventure in Chinese style"}'
```

#### Debug based on API

**Create a session:**

```bash
curl --location --request POST 'https://xxxxx.apigateway-cn-beijing.volceapi.com/apps/storybook_illustrator/users/u_123/sessions/s_124' \
--header 'Content-Type: application/json' \
--header 'Authorization: <your_api_key>' \
--data ''
```

**Send a message:**

```bash
curl --location 'https://xxxxx.apigateway-cn-beijing.volceapi.com/run_sse' \
--header 'Authorization: <your_api_key>' \
--header 'Content-Type: application/json' \
--data '{
    "appName": "storybook_illustrator",
    "userId": "u_123",
    "sessionId": "s_124",
    "newMessage": {
        "role": "user",
        "parts": [{
            "text": "Please generate a storybook video based on the fable 《The Fox and the Tiger》"
        }]
    },
    "streaming": false
}'
```

## Directory Structure

```bash
03_video_gen/
├── agent.py              # Agent entry point, includes MCP integration
├── agent.yaml            # Agent configuration (model, instructions, tools)
├── tool/                 # Custom tool implementations
│   ├── file_download.py  # Batch file download tool
│   └── tos_upload.py     # TOS upload and signed URL generation
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project configuration (uv/pip dependencies and metadata)
├── __init__.py           # Package initialization file
├── .python-version       # Python version declaration (development environment)
├── README.md            # Project documentation
└── .dockerignore         # Docker build exclusions
```

## Demonstration

Video generation effect demonstration.

## FAQ

**Error: `npx` command not found**

- Install Node.js 18+ and npm
- Verify that `npx --version` runs correctly in the terminal

**TOS upload failed:**

- Confirm that `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` are set
- Verify that your account has TOS bucket access permissions

**MCP tool connection error:**

- Ensure that the default MCP port does not conflict with other services
- Check the Node.js process logs for detailed error messages

**Using a custom TOS bucket:**

- Set via environment variable: `export DATABASE_TOS_BUCKET="agentkit-platform-{{account_id}}"`
- Or modify the default value in [`tool/tos_upload.py`](tool/tos_upload.py)

**`uv sync` failed:**

- Ensure that Python 3.12+ is installed
- Check if the `.python-version` file matches your installed Python version
- Try rebuilding the dependencies with `uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple --refresh`

## 🔗 Related Resources

- [AgentKit Official Documentation](https://www.volcengine.com/docs/86681/1844878?lang=en)
- [TOS Object Storage](https://www.volcengine.com/product/TOS)
- [AgentKit Console](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/overview?projectName=default)
- [Volcano Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)

## Code License

This project is licensed under the Apache 2.0 License
