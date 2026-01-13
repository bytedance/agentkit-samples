# E-commerce Marketing Video Generation

## Overview

> This project implements e-commerce marketing video generation through A2A-enabled Multi-Agents. The system consists of four agents: marketing planning, video director, evaluation, and composition & publishing. It provides an end-to-end solution from video creative conception, high-quality video generation, to video launch and publication. It is aimed at e-commerce customers or marketing teams who need to quickly and batch-produce short marketing videos, with the goal of lowering the barrier to video production and improving the efficiency of marketing content production.

## Core Features

This project provides the following core features:

- **Intelligent Marketing Planning**: Automatically analyzes product information to generate marketing strategies and creative plans.
- **Multi-modal Content Generation**: Supports intelligent generation of various media formats such as text, images, and videos.
- **Quality Assessment and Optimization**: Ensures the quality of generated content through an AI evaluation mechanism.
- **One-click Publishing Service**: Provides a complete video composition and publishing solution.

## Agent Capabilities

The system includes 4 core agents, each with its own responsibilities:

- **Marketing Planning Agent (market-agent)**: Responsible for parsing user input (such as product links), conducting market analysis, and forming preliminary marketing strategies and video creatives.
- **Video Director Agent (director-agent)**: Generates specific video scripts and copy based on the marketing strategy, and calls on multi-modal capabilities (text-to-image, image-to-video) to produce video materials.
- **Evaluation Agent (evaluate-agent)**: Conducts quality assessment and screening of the generated video materials, and uses an autonomous evaluation mechanism for optimization to ensure video quality.
- **Composition & Publishing Agent (release-agent)**: Composes the screened materials into a final video and provides publishing capabilities.

### Cost Description

| Service | Description | Billing Information |
| --- | --- | --- |
| [Doubao-Seed-1.6](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seed-1-6) | Responsible for understanding user information and converting it into tool calls. | [Multiple billing methods](https://www.volcengine.com/docs/82379/1099320) |
| [Doubao-Seedance 1.0 pro](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedance-1-0-pro) | Responsible for converting images and text descriptions into videos. | [Multiple billing methods](https://www.volcengine.com/docs/82379/1099320) |
| [Doubao-Seedream 4.5 pro](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedream-4-5) | Responsible for generating images based on text or reference images. | [Multiple billing methods](https://www.volcengine.com/docs/82379/1099320) |

## Local Execution

### Environment Preparation

Before you begin, please ensure that your development environment meets the following requirements:

- Python 3.10 or higher
- VeADK 0.2.28 or higher
- Playwright 1.55.0 or higher
- It is recommended to use `uv` for dependency management.
- <a target="_blank" href="https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey">Get Volcano Ark API KEY</a>
- <a target="_blank" href="https://console.volcengine.com/iam/keymanage/">Get Volcano Engine AK/SK</a>

### Quick Start

Follow the steps below to deploy and run this project locally.

#### 1. Download the code and install dependencies

```bash
# Clone the code repository
git clone https://github.com/volcengine/agentkit-samples.git
cd python/02-use-cases/04_ad_video_gen_a2a

# Install project dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 2. Configure environment variables

This project contains multiple Agents, and each Agent requires separate configuration. Please refer to the `config.yaml.example` file to create a `config.yaml` for each Agent and fill in the necessary key information.

Taking `director-agent` as an example:

```bash
# Enter the director-agent directory
cd app/director-agent

# Copy the configuration file
cp config.yaml.example config.yaml
```

Then, edit the `config.yaml` file and fill in your Volcano Ark API Key, Volcano Engine AK/SK, and other information. Please repeat this operation for `market-agent`, `evaluate-agent`, `release-agent`, and `multimedia-agent`.

For specific configuration items, please refer to the <a target="_blank" href="https://github.com/volcengine/veadk-python/blob/main/config.yaml.full">veadk-python config.yaml configuration document</a>.

#### 3. Install Playwright browser components

`market-agent` requires Playwright to parse web page content.

```bash
# market-agent
# Install Playwright browser dependencies

playwright install
```

#### 4. Start the services

Please start each Agent service in order.

```bash
# Activate the virtual environment
# Windows (Powershell)
# .\.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

# Start market-agent
cd python/02-use-cases/04_ad_video_gen_a2a/app/market-agent/src
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --loop asyncio

# Start director-agent
cd python/02-use-cases/04_ad_video_gen_a2a/app/director-agent/src
python -m uvicorn app:app --host 127.0.0.1 --port 8001 --loop asyncio

# Start evaluate-agent
cd python/02-use-cases/04_ad_video_gen_a2a/app/evaluate-agent/src
python -m uvicorn app:app --host 127.0.0.1 --port 8002 --loop asyncio

# Start release-agent
cd python/02-use-cases/04_ad_video_gen_a2a/app/release-agent/src
python -m uvicorn app:app --host 127.0.0.1 --port 8003 --loop asyncio

# Finally, start multimedia-agent
cd python/02-use-cases/04_ad_video_gen_a2a/app/multimedia-agent/src
python -m uvicorn server:app --host 127.0.0.1 --port 8004 --loop asyncio

# Start the short_link service
cd python/02-use-cases/04_ad_video_gen_a2a/app/short_link
python -m uvicorn app:app --host 127.0.0.1 --port 8005 --loop asyncio
```

#### 5. Test the service

After all services have started, you can run the test script to verify.

```bash
python app/main.py
```

## AgentKit Deployment

> todo

### Technical Implementation

At the core of this project is a multi-Agent collaboration framework built on VeADK. Each Agent has clear responsibilities and works together through A2A (Agent-to-Agent) communication to complete the entire process from understanding requirements to video publication.

- **Marketing Planning Agent (`market-agent`)**: Responsible for parsing user input (such as product links), conducting market analysis, and forming preliminary marketing strategies and video creatives.
- **Video Director Agent (`director-agent`)**: Generates specific video scripts and copy based on the marketing strategy, and calls on multi-modal capabilities (text-to-image, image-to-video) to produce video materials.
- **Evaluation Agent (`evaluate-agent`)**: Conducts quality assessment and screening of the generated video materials, and uses an autonomous evaluation mechanism for optimization to ensure video quality.
- **Composition & Publishing Agent (`release-agent`)**: Composes the screened materials into a final video and provides publishing capabilities.

## Directory Structure

```plaintext
/
├── README.md                 # This document
├── backend/app/
│   ├── __init__.py
│   ├── director-agent/       # Video Director Agent
│   │   ├── config.yaml.example # Example configuration file
│   │   └── src/                # Agent source code
│   ├── evaluate-agent/       # Evaluation Agent
│   │   ├── config.yaml.example
│   │   └── src/
│   ├── main.py                 # Main program for testing
│   ├── market-agent/         # Marketing Planning Agent
│   │   ├── config.yaml.example
│   │   └── src/
│   ├── multimedia-agent/       # Main Agent, responsible for coordinating other Agents
│   │   ├── config.yaml.example
│   │   └── src/
│   ├── release-agent/        # Publishing Agent
│   │   ├── config.yaml.example
│   │   └── src/
│   └── short_link/           # Video short link generation tool
│       ├── app.py
│       └── requirements.txt
└── ... (other project files)
```

## Example Prompts

Here are some common prompt examples:

- `Generate a video for me based on the product information on this website https://...`
- `Create a 30-second marketing video for this dress`
- `Generate a short video introducing the features of a phone case`
- `Create a promotional video based on this product link`

## Demonstration

The system is capable of:

- ✅ Automatically parsing product information and generating marketing strategies
- ✅ Creating high-quality video scripts and storyboards
- ✅ Generating engaging marketing copy
- ✅ Producing professional e-commerce marketing videos
- ✅ Providing video quality assessment and optimization
- ✅ Supporting one-click publishing to multiple platforms

## FAQ

A list of frequently asked questions is to be added.

## Code License

This project is licensed under an open-source license. For details, please refer to the LICENSE file in the project's root directory.
