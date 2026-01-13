# NaviGo AI - Real-time Voice Assistant Agent

This is an introductory real-time voice assistant Agent built based on Volcano Engine's VeADK and AgentKit, demonstrating how to create an AI Agent with travel planning capabilities.

## Overview

This example showcases the integration of AgentKit with the Doubao end-to-end real-time speech large model.

## Core Features

- Create a simple real-time voice assistant Agent. Real-time voice chat requires handling multiple tasks simultaneously: listening, thinking, and speaking.
- The Doubao end-to-end real-time speech large model API, i.e., RealtimeAPI, supports low-latency, multi-modal interaction, and can be used to build voice-to-voice conversation tools.

## Agent Capabilities

```text
User Message
    ↓
AgentKit Runtime
    ↓
NaviGo AI Agent
    ├── VeADK Agent (Dialogue Engine)
    └── End-to-end real-time speech large model (LLM)
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/07_realtime_voice/agent.py) - Main application, defines how the Agent handles audio and text transcription. |
| **Test Client** | [interface.html](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/07_realtime_voice/client/interface.html) - Real-time voice assistant interface implemented based on HTML5. |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/07_realtime_voice/pyproject.toml) - Dependency management (uv tool). |
| **AgentKit Configuration** | agentkit.yaml - Cloud deployment configuration file. |

### Code Features

**Agent Definition** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/07_realtime_voice/agent.py#L38-L42)):

```python
agent = Agent(
    name="voice_assistant_agent",
    model=MODEL,
    instruction=SYSTEM_INSTRUCTION,
)
```

**Voice Configuration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/07_realtime_voice/agent.py#L72-L84)):

```python
# Create run config with audio settings
run_config = RunConfig(
    streaming_mode=StreamingMode.BIDI,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=VOICE_NAME
            )
        )
    ),
    response_modalities=["AUDIO"],
    output_audio_transcription=types.AudioTranscriptionConfig(),
    input_audio_transcription=types.AudioTranscriptionConfig(),
)
```

## Directory Structure Description

```bash
07_realtime_voice/
├── agent.py           # Agent application entry point
├── core_utils.py      # Core utility functions (e.g., audio processing)
├── client/            # Test client directory
│   ├── interface.html # Real-time voice assistant interface (HTML5 + WebSocket)
├── requirements.txt   # Python dependency list (required for agentkit deployment)
├── pyproject.toml     # Project configuration (uv dependency management)
├── agentkit.yaml      # AgentKit deployment configuration (auto-generated after running agentkit config)
├── Dockerfile         # Docker image build file (auto-generated after running agentkit config)
└── README.md          # Project documentation
```

## Local Execution

### Prerequisites

**1. Activate Doubao Real-time Speech Model Service:**

- Visit [Volcano Engine Console](https://console.volcengine.com/speech/new/setting/activate?projectName=default)
- Activate the end-to-end real-time speech model service

**2. Obtain APP_ID and API_KEY:**

- Refer to [Console FAQ](https://www.volcengine.com/docs/6561/196768?lang=zh#q1%EF%BC%9A%E5%93%AA%E9%87%8C%E5%8F%AF%E4%BB%A5%E8%8E%B7%E5%8F%96%E5%88%B0%E4%BB%A5%E4%B8%8B%E5%8F%82%E6%95%B0appid%EF%BC%8Ccluster%EF%BC%8Ctoken%EF%BC%8Cauthorization-type%EF%BC%8Csecret-key-%EF%BC%9F) to get APP_ID and API_KEY

**3. Obtain Volcano Engine Access Credentials:**

- Refer to [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get AK/SK

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
cd python/01-tutorials/01-agentkit-runtime/07_realtime_voice
```

Use the `uv` tool to install the project dependencies:

```bash
# If you don't have a `uv` virtual environment, you can create one first
uv venv --python 3.12

# Use `pyproject.toml` to manage dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate
```

### Environment Preparation

```bash
# Doubao end-to-end real-time speech large model name
export MODEL=doubao_realtime_voice_model
# Doubao end-to-end real-time speech large model APP_ID and API_KEY
export MODEL_REALTIME_APP_ID=<Your APP_ID>
export MODEL_REALTIME_API_KEY=<Your API_KEY>

# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Debugging Methods

#### Method 1: Command-line Test

```bash
cd python/01-tutorials/01-agentkit-runtime/07_realtime_voice

# Start the Agent service
uv run agent.py
# The service will listen on http://0.0.0.0:8000

# Open a new client
# Open client/interface.html in your browser, the client will automatically connect to the WebSocket server.
```

**Running Effect**:

![NaviGo AI](../../../assets/images/navigo_ai.png)

## AgentKit Deployment

### Prerequisites

**Important Note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the case can be executed normally.

**1. Activate Doubao Real-time Speech Model Service:**

- Visit [Volcano Engine Console](https://console.volcengine.com/speech/new/setting/activate?projectName=default)
- Activate the end-to-end real-time speech model service

**2. Obtain APP_ID and API_KEY:**

- Refer to [Console FAQ](https://www.volcengine.com/docs/6561/196768?lang=zh#q1%EF%BC%9A%E5%93%AA%E9%87%8C%E5%8F%AF%E4%BB%A5%E8%8E%B7%E5%8F%96%E5%88%B0%E4%BB%A5%E4%B8%8B%E5%8F%82%E6%95%B0appid%EF%BC%8Ccluster%EF%BC%8Ctoken%EF%BC%8Cauthorization-type%EF%BC%8Csecret-key-%EF%BC%9F) to get APP_ID and API_KEY

**3. Obtain Volcano Engine Access Credentials:**

- Refer to [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get AK/SK

### AgentKit Cloud Deployment

```bash
cd python/01-tutorials/01-agentkit-runtime/07_realtime_voice

# Configure deployment parameters
agentkit config

# Start the cloud service
agentkit launch

# Test the deployed Agent
# You need to edit client/interface.html and change ws://localhost:8000 on line 168 to the runtime_endpoint field generated in agentkit.yaml
# Open client/interface.html in your browser, the client will automatically connect to the WebSocket server.
```

## Example Prompts

## Effect Demonstration

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Doubao Real-time Speech Model Service](https://www.volcengine.com/docs/6561/1594356)

## Code License

This project is licensed under the Apache 2.0 License.
