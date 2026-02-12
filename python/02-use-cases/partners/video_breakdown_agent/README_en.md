# Video Breakdown Analyzer

## Overview

This is an intelligent short-video analysis system built on Volcengine VeADK & AgentKit. The system adopts a Multi-Agent architecture, integrating FFmpeg video processing, Volcengine ASR speech recognition, LiteLLM multimodal vision analysis, and TOS object storage, capable of comprehensive professional analysis of short videos.

## Core Features

This project provides the following core capabilities:

- **Video Scene Segmentation**: Automatically identifies video scenes based on FFmpeg, extracts key frames and analyzes visual content, outputting structured scene data
- **First 3-Second Hook Analysis**: Professional scoring from 5 dimensions: visual impact, language hooks, emotional arousal, information density, and rhythm control
- **Professional Report Generation**: Integrates scene data and hook analysis results to generate complete analysis reports in Markdown format
- **Web Search**: Real-time access to the latest short-video industry information, platform rules, and trending topics

## Agent Architecture

![Video Breakdown Agent with AgentKit Runtime](assets/architecture_video_breakdown_agent.jpg)

```text
User Input (Video URL/Local File)
    ↓
AgentKit Runtime
    ↓
Root Agent (XiaoShi - Main Orchestrator)
    ├── Breakdown Agent (Scene Segmentation)
    │   ├── FFmpeg Video Preprocessing
    │   ├── Volcengine ASR Speech Recognition
    │   ├── LiteLLM Vision Analysis
    │   └── BGM Analysis
    ├── Hook Analyzer Agent (Hook Analysis)
    │   ├── First 3-Second Scene Extraction
    │   ├── Multimodal Vision Scoring
    │   └── JSON Formatting
    ├── Report Generator Agent (Report Generation)
    └── Search Agent (Web Search)
```

Main Volcengine products and Agent components:

- Ark LLM Platform:
  - doubao-seed-1-6-251015 (primary reasoning model)
  - doubao-seed-1-6-vision-250815 (vision analysis model)
- TOS Object Storage
- Volcengine ASR Speech Recognition (optional)
- Web Search
- AgentKit
- APMPlus (optional observability)

Third-party dependencies:

- FFmpeg (auto-packaged via imageio-ffmpeg, no manual installation required)
- LiteLLM (supports Gemini, Doubao, GPT-4o and other vision models)

## Usage Examples

Below is a typical workflow from web search to in-depth video breakdown.

### 1. Web Search (Weather/Industry Info)

**User:** Weather in Hangzhou

**XiaoShi (Root Agent):** Based on the search results, here is the current weather and forecast for Hangzhou:

📍 **Hangzhou Weather (Wednesday, Feb 11, 2026)**

**Current Conditions**
- **Temperature**: 13°C (Current), 5~15°C for the day
- **Condition**: Sunny
- **Wind**: North 4 (turning West in the afternoon)
- **Humidity**: 36%
- **Air Quality**: AQI 64 (Good)

**📅 3-Day Forecast**

| Date | Condition | Temp Range | Wind |
| :--- | :--- | :--- | :--- |
| Feb 11 (Wed) | Sunny | 5~15°C | North to West 2-4 |
| Feb 12 (Thu) | Sunny | 6~16°C | SE 2 |
| Feb 13 (Fri) | Cloudy | 8~20°C | South 2 |

---

### 2. Video Breakdown

**User:** http://example.com/sample-video.mp4

**XiaoShi (Root Agent):** Sure, I'll break down the scenes for you.

#### 🎥 Video Breakdown Results

**Video Info**
- **Duration**: 17.07s
- **Resolution**: 720x960
- **Frame Rate**: 60fps

**Scene List**

| ID | Time | Shot | Movement | Content Description | Audio | Tags |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 0.0-3.0s | CU | Static | Showing a beige LocknLock bottle; transitioning to opening the lid. | None | Product Display |
| 2 | 3.0-5.0s | CU | Static | Pouring water into the bottle; home lifestyle background. | None | Product Display |

**BGM Analysis**
- **BGM**: Yes
- **Style**: Soft Piano/Ambient (Healing, Minimalist)
- **Mood**: Relaxing (Positive)

---

### 3. Hook Analysis

**User:** Analyze the first 3 seconds hook in detail.

**XiaoShi (Root Agent):** 

#### 🪝 First 3s Hook Analysis & Rating

**Hook Elements**
- **Visual Hook**: Close-up focusing on the handle design; "Grip-and-Lift" action reinforces convenience.
- **Auditory Hook**: Soothing piano/violin (60-80 BPM) creates a cozy atmosphere.
- **Content Hook**: Completes the "What it is -> How to use" loop within 3s.

**Rating**

| Dimension | Score (1-10) | Analysis |
| :--- | :--- | :--- |
| Visual Attraction | 8.5 | Sharp focus, smooth and purposeful movements. |
| Info Efficiency | 9.0 | Delivers core value proposition within 3s. |

---

### 4. Generate Insight Report

**User:** Give me a detailed video insight report.

**XiaoShi (Root Agent):** 

#### 📊 LocknLock Product Display Insight Report

**1. Content Structure**
The video follows a "General -> Detail -> Scenario -> Extension" logic, forming a complete product perception chain.

**2. User Attention**
- **Peak Attention**: 0-5s (Frequent actions, clear visual focus).
- **Risk Point**: 10-17s (Product transition lacks smooth bridge).

**3. Optimization Suggestions**
- **Visual**: Add a "Leak-proof test" close-up.
- **Audio**: Add crisp sound effects for lid opening.
- **Content**: Overlay text tags like "Food-grade 304 Stainless Steel".

## Directory Structure

```bash
video_breakdown_agent/
├── README.md                   # Project documentation (Chinese)
├── README_en.md                # Project documentation (English)
├── README_CONFIG.md            # Detailed configuration guide
├── project.toml                # Application marketplace metadata
├── agent.py                    # AgentKit deployment entry
├── requirements.txt            # pip dependencies
├── pyproject.toml              # uv project configuration
├── config.yaml                 # Configuration file (example, actual keys injected via env vars)
├── config.yaml.example         # Configuration template
├── deploy.sh                   # Deployment script
├── video_breakdown_agent/      # Python package (core code)
│   ├── agent.py                # Root Agent definition
│   ├── prompt.py               # Main orchestration prompt
│   ├── sub_agents/             # Sub Agents
│   │   ├── breakdown_agent/    # Scene segmentation Agent
│   │   ├── hook_analyzer_agent/# Hook analysis Agent (SequentialAgent)
│   │   └── report_generator_agent/  # Report generation Agent
│   ├── tools/                  # Tool functions
│   │   ├── process_video.py    # Video preprocessing (FFmpeg + ASR)
│   │   ├── analyze_segments_vision.py  # Vision analysis
│   │   ├── analyze_bgm.py      # BGM analysis
│   │   ├── analyze_hook_segments.py    # Hook scene extraction
│   │   ├── report_generator.py # Report generation
│   │   └── video_upload.py     # TOS video upload
│   ├── hook/                   # Callback hooks
│   │   ├── format_hook.py      # JSON repair
│   │   └── video_upload_hook.py# File upload interceptor
│   └── utils/                  # Utility classes
│       └── types.py            # Pydantic data models
└── img/                        # Architecture diagrams and screenshots
```

## Local Development

### Prerequisites

**Python Version:**

- Python 3.12 or higher

**1. Enable Volcengine Ark Model Service:**

- Visit [Volcengine Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview)
- Enable model inference service
- Create API Key (used for `MODEL_AGENT_API_KEY`)

**2. Create TOS Bucket (for video upload):**

- Visit [TOS Console](https://console.volcengine.com/tos/bucket)
- Create a new bucket (e.g., `video-breakdown-uploads`)
- Set region to `cn-beijing`
- Configure public read permissions (or use pre-signed URLs)

**3. Obtain Volcengine Access Keys:**

- Visit [IAM Key Management](https://console.volcengine.com/iam/keymanage/)
- Create Access Key/Secret Key (used for `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY`)

**4. (Optional) Configure ASR Service:**

- Visit [Speech Service](https://console.volcengine.com/speech/service/list) to obtain App ID and Access Key
- If not configured, the system will gracefully degrade (skip speech recognition)

### Dependency Installation

**Method 1: Using pip**

```bash
pip install -r requirements.txt
```

**Method 2: Using uv (recommended)**

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Environment Configuration

**Method 1: Create `.env` file (recommended for local development)**

```bash
# Copy configuration template
cp config.yaml.example config.yaml

# Edit .env file and fill in the following required environment variables:
MODEL_AGENT_API_KEY=your_ark_api_key
VOLCENGINE_ACCESS_KEY=your_volcengine_ak
VOLCENGINE_SECRET_KEY=your_volcengine_sk
DATABASE_TOS_BUCKET=your_tos_bucket_name
DATABASE_TOS_REGION=cn-beijing

# Optional: ASR configuration (graceful degradation if not configured)
ASR_APP_ID=your_asr_app_id
ASR_ACCESS_KEY=your_asr_access_key

# Optional: Vision model configuration (defaults to Doubao if not configured)
MODEL_VISION_NAME=doubao-seed-1-6-vision-250815
# Or use Gemini:
# MODEL_VISION_NAME=gemini/gemini-2.5-pro
# GEMINI_API_KEY=your_gemini_api_key
```

**Method 2: Use environment variables directly**

```bash
export MODEL_AGENT_API_KEY=your_ark_api_key
export VOLCENGINE_ACCESS_KEY=your_volcengine_ak
export VOLCENGINE_SECRET_KEY=your_volcengine_sk
export DATABASE_TOS_BUCKET=your_tos_bucket_name
```

**Priority**: System environment variables > `.env` file > `config.yaml`

For detailed configuration instructions, see [README_CONFIG.md](README_CONFIG.md).

### Running the Application

**Method 1: Local debugging with veadk web (recommended)**

```bash
# veadk automatically discovers video_breakdown_agent/ package
uv run veadk web
```

Access `http://localhost:8000` to interact with the Agent.

**Method 2: Run directly**

```bash
python agent.py
```

**Method 3: Smoke test**

```bash
# Quick test
uv run python .scripts/smoke_test.py "Hello"

# Full pipeline test
uv run python .scripts/smoke_test.py --pipeline-cases
```

## AgentKit Deployment

### Prerequisites

**Install AgentKit CLI:**

```bash
pip install agentkit
```

### One-Click Deployment

**1. Initialize configuration:**

```bash
# Configure AgentKit credentials
agentkit config --account-id YOUR_ACCOUNT_ID --access-key YOUR_AK --secret-key YOUR_SK
```

**2. Deploy to cloud:**

```bash
# Deploy (automatically creates Runtime, builds image, deploys)
agentkit launch

# View deployment status
agentkit status

# View Runtime logs
agentkit logs
```

**3. Configure environment variables in console:**

After deployment, you need to configure the following environment variables in the [AgentKit Console](https://console.volcengine.com/agentkit):

- `MODEL_AGENT_API_KEY`: Ark API Key
- `VOLCENGINE_ACCESS_KEY`: Volcengine Access Key
- `VOLCENGINE_SECRET_KEY`: Volcengine Secret Key
- `DATABASE_TOS_BUCKET`: TOS bucket name
- `DATABASE_TOS_REGION`: TOS region (default: `cn-beijing`)

**4. Test deployment:**

```bash
# Test using agentkit CLI
agentkit run "Analyze this video: https://example.com/video.mp4"
```

### Advanced Deployment Options

**Custom Docker build:**

```bash
# Build image locally
docker build -t video-breakdown-agent:latest .

# Run container
docker run -p 8000:8000 \
  -e MODEL_AGENT_API_KEY=your_key \
  -e VOLCENGINE_ACCESS_KEY=your_ak \
  -e VOLCENGINE_SECRET_KEY=your_sk \
  video-breakdown-agent:latest
```

**Deployment script:**

```bash
# Use built-in deployment script
./deploy.sh
```

For detailed deployment instructions, see [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md).

## Key Features

### 1. Multi-Agent Architecture

- **Root Agent**: Main orchestrator, responsible for understanding user intent and dispatching sub-agents
- **Breakdown Agent**: Video preprocessing + vision analysis + BGM analysis
- **Hook Analyzer Agent**: SequentialAgent (vision scoring → JSON formatting)
- **Report Generator Agent**: Markdown report generation
- **Search Agent**: Real-time web search

### 2. Powerful Vision Analysis

- LiteLLM unified routing supporting multiple vision models:
  - Volcengine Doubao Vision
  - Google Gemini 2.5 Pro
  - OpenAI GPT-4o
- Switch models with one line of configuration, no code changes required

### 3. Graceful Degradation

- **TOS upload failure**: Automatically falls back to base64 encoding
- **ASR not configured**: Automatically skips speech recognition
- **Vision analysis failure**: Attempts model fallback
- **Hook analysis failure**: Still generates basic scene reports

### 4. Production-Ready

- Complete error handling and logging
- OpenTelemetry observability support (APMPlus/CozeLoop/TLS)
- Docker containerization
- AgentKit one-click deployment

## Sample Prompts

**Basic scene segmentation:**
```
Analyze the scene structure of this video
```

**Hook analysis:**
```
Analyze the hook effectiveness of the first 3 seconds of this video and provide professional scoring
```

**Complete analysis:**
```
Generate a complete video analysis report
```

**Search information:**
```
What are the latest Douyin recommendation algorithm rules?
```

## Demo

[Demo screenshots or videos will be placed in the `img/` directory]

## FAQ

**Q1: Does FFmpeg need to be installed manually?**

A: No. This project uses `imageio-ffmpeg` which automatically downloads and packages FFmpeg binaries. If you have system FFmpeg installed, it will be used preferentially.

**Q2: Does the system support platforms like Douyin/Xiaohongshu/Bilibili links?**

A: Currently only public HTTP/HTTPS video download links are supported. Platform-specific links need to be extracted to download URLs first.

**Q3: What should I do if TOS upload fails?**

A: The system will automatically fall back to base64 encoding to continue analysis. Check:
- Whether `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` are correctly configured
- Whether TOS bucket permissions are correct (recommend public read or pre-signed URLs)

**Q4: What should I do if vision analysis fails?**

A: Check:
- Whether `MODEL_AGENT_API_KEY` is correctly configured
- Whether the vision model name is correct (must include date suffix, e.g., `doubao-seed-1-6-vision-250815`)
- Whether network can access the model endpoint

**Q5: What should I do if ASR speech recognition fails?**

A: ASR is optional. The system will automatically skip speech recognition and continue with vision analysis if not configured. To enable ASR, configure:
```bash
ASR_APP_ID=your_app_id
ASR_ACCESS_KEY=your_access_key
```

**Q6: How to switch vision models?**

A: Modify environment variable `MODEL_VISION_NAME`:

```bash
# Use Doubao (default)
MODEL_VISION_NAME=doubao-seed-1-6-vision-250815

# Use Gemini
MODEL_VISION_NAME=gemini/gemini-2.5-pro
GEMINI_API_KEY=your_gemini_api_key

# Use GPT-4o
MODEL_VISION_NAME=gpt-4o
OPENAI_API_KEY=your_openai_api_key
```

**Q7: Are there any limits on video duration?**

A: Recommended:
- Video duration: 15 seconds to 3 minutes
- File size: <100MB
- Resolution: 720p or 1080p

Longer videos will require more processing time and model tokens.

## References

- [VeADK Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Documentation](https://www.volcengine.com/docs/6459)
- [Volcengine Ark Platform](https://console.volcengine.com/ark)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)

## Contributing

Contributions are welcome! Please refer to [CONTRIBUTING.md](../../CONTRIBUTING.md) for contribution guidelines.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
