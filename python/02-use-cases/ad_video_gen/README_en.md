# E-commerce Marketing Video Generation

## Overview

> This project uses VeADK and AgentKit to generate e-commerce marketing videos. After the user provides product information such as product name, selling points, target audience, usage scenarios, style preferences, and an optional product image URL, a single Agent first generates a 2x2 marketing story reference image, then generates a complete product marketing short video from that reference image.
>
> This sample uses a single-agent architecture. It directly calls the built-in `image_generate` and `video_generate` tools to complete the workflow: marketing story planning, reference image generation, image-to-video generation, and result preview. It is designed as a lightweight end-to-end sample for e-commerce marketing video generation.

- This project is designed for AgentKit platform deployment and is suitable for product showcase, campaign promotion, and brand seeding short-video generation.
- The project exposes one Root Agent as the service entry point, making it easy to debug locally, deploy to the cloud, and customize.
- The project does not include complex post-processing such as candidate generation, quality evaluation, video stitching, or TOS upload. It focuses on a lightweight end-to-end generation flow.

## Key Features

This project provides the following capabilities:

- **Product information understanding**: understands marketing requirements from product name, selling points, target audience, usage scenarios, and style preferences
- **Marketing story planning**: automatically designs a 4-part marketing story covering hook, scenario, selling point highlight, and call-to-action
- **2x2 reference image generation**: calls the built-in image generation tool to create one 2x2 marketing story reference image that aligns product appearance, visual style, and narrative structure
- **Product image reference input**: supports publicly accessible product image URLs and tries to preserve product appearance, package structure, and main colors during image generation
- **Image-to-video generation**: calls the built-in video generation tool to generate a default 9:16, 1080P, 15-second marketing short video from the reference image
- **Preview-ready output**: returns the result with Markdown image syntax and an HTML video tag, so it can be previewed directly in the AgentKit debug page or a web page

## Agent Capabilities

The system exposes one Root Agent. Internally, the Prompt constraints and tool calls complete the full video generation workflow:

- **Marketing planning**: parses user input and extracts product name, selling points, audience, scenario, style, and aspect ratio
- **Storyboard planning**: organizes the marketing request into a 4-part story and maps it to the 2x2 reference image
- **Image generation**: calls `image_generate` to generate one 2x2 reference image; if the user provides product image URLs, they are passed as image-to-image references
- **Video generation**: calls `video_generate`, using the 2x2 reference image as `reference_images`, to generate a continuous marketing short video
- **Result formatting**: returns the intermediate reference image first, then the final video, making the process observable and the result easy to preview

### Cost Notes

| Related Service | Description | Pricing |
| --- | --- | --- |
| DeepSeek V4 Pro (`deepseek-v4-pro-260425`) | Understands user input, plans the marketing story, and converts it into tool calls. | [Model details and pricing](https://docs.byteplus.com/en/docs/ModelArk/1108216) |
| Doubao Seedream 5.0 pro (`doubao-seedream-5-0-pro-260628`) | Generates the 2x2 marketing story reference image from text or product image references. | [Model details and pricing](https://docs.byteplus.com/en/docs/ModelArk/1108216) |
| Doubao Seedance 2.0 (`doubao-seedance-2-0-260128`) | Generates the marketing short video from the 2x2 reference image and video description. | [Model details and pricing](https://docs.byteplus.com/en/docs/ModelArk/1108216) |

## Run Locally

### Prerequisites

Before starting, make sure your environment meets these requirements:

- Python 3.12 or later
- veadk-python 0.5.37 (see `pyproject.toml`)
- agentkit-sdk-python 0.5.10 (see `pyproject.toml`)
- `uv` is recommended for dependency management
- <a target="_blank" href="https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey">Get a BytePlus ModelArk API key</a>

### Quick Start

Follow these steps to set up and run the project locally.

#### 1. Clone and install dependencies

```bash
# Clone the repository
git clone https://github.com/bytedance/agentkit-samples.git
cd agentkit-samples/python/02-use-cases/ad_video_gen

# Install dependencies
uv sync --index-url https://mirrors.aliyun.com/pypi/simple

# macOS or Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\activate
```

#### 2. Configure environment variables

For local debugging, configure models and API keys directly through environment variables.

```bash
# Main model
export MODEL_AGENT_NAME=deepseek-v4-pro-260425
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
export MODEL_AGENT_API_KEY=<Your Ark API Key>

# Image generation model
export MODEL_IMAGE_NAME=doubao-seedream-5-0-pro-260628
export MODEL_IMAGE_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
export MODEL_IMAGE_API_KEY=<Your Ark API Key>

# Video generation model
export MODEL_VIDEO_NAME=doubao-seedance-2-0-260128
export MODEL_VIDEO_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
export MODEL_VIDEO_API_KEY=<Your Ark API Key>
```

#### 3. Local debugging

Use `veadk web` for local debugging. Following the VeADK Web app discovery convention, start the service from the parent `python/02-use-cases` directory:

```bash
cd ..
veadk web
```

By default it listens on `http://0.0.0.0:8000`.

## AgentKit Deployment

To generate the deployment configuration, run the following command in this directory:

```bash
agentkit config \
    --agent_name ad_video_gen \
    --entry_point agent.py \
    --launch_type cloud \
    --image_tag v1.0.0
```

After the command finishes, `agentkit.yaml` will be generated in the current directory.

Deploy to runtime:

```bash
agentkit launch
```

`agentkit launch` builds the runtime artifacts from the deployment configuration and generates `Dockerfile` in the current directory.

For local container deployment, set `--launch_type` to `local`, or follow the AgentKit CLI prompts and choose local deployment.

## Technical Details

At its core, this project is a single-agent workflow built with VeADK. The Root Agent handles requirement understanding, prompt planning, and tool orchestration:

User input → Marketing story planning → 2x2 reference image generation → Intermediate reference image preview → Image-to-video generation → Image and video preview output

The generation flow calls `image_generate` once and `video_generate` once:

- `image_generate` creates one 2x2 reference image containing 4 storyboard scenes
- `video_generate` uses the 2x2 reference image as `reference_images` and generates one continuous marketing short video

## Directory Structure

```plaintext
/
├── README.md                 # Chinese documentation
├── README_en.md              # English documentation
├── agent.py                  # AgentKit service entry and root_agent definition
├── prompt.py                 # Main single-agent Prompt
├── pyproject.toml            # Dependency management (uv)
├── requirements.txt          # Dependency management (pip/uv pip)
├── agentkit.yaml             # AgentKit deployment configuration (generated after running agentkit config)
└── Dockerfile                # Image build file (generated after running agentkit launch)
```

## Example Prompts

Here are some commonly used prompt examples:

- `Please generate a product showcase video for a bayberry drink, vertical 9:16, fresh summer style. Selling points: natural bayberry, sweet and sour, refreshing when chilled, suitable for hot pot, barbecue, and gatherings. Product image: https://ark-tutorial.tos-cn-beijing.volces.com/multimedia/%E6%9D%A8%E6%A2%85%E9%A5%AE%E6%96%99.jpg`
- `Please generate an e-commerce marketing video for milky soft pull-apart toast. Usage scenarios: breakfast, afternoon tea, camping picnic. Key selling points: rich milky aroma, soft texture, crispy outside and soft inside after toasting, suitable for family sharing. Style: warm, bright, appetizing.`
- `Generate a 15-second product seeding video for a wabi-sabi scented candle. Target audience: urban professionals who like minimalist home decor and bedtime relaxation. Selling points: natural soy wax, woody scent, reusable cement jar. Visual style: restrained, quiet, premium.`

## Demo Output

The system can:

- Automatically parse product information and generate a marketing story structure
- Create a 2x2 marketing story reference image
- Generate a continuous product marketing short video from the reference image
- Use product image URLs as image-to-image references
- Preview image and video results directly in the AgentKit debug page

## FAQ

### Does it support direct image upload or base64 images?

The current sample only supports publicly accessible image URLs as product references. Direct image upload and base64 images are not supported.

### Does it generate multiple candidate videos and evaluate them automatically?

The current single-agent version generates one reference image and one video by default. It does not include candidate generation, quality evaluation, stitching, or upload workflows.

### Can the video aspect ratio and duration be adjusted?

Yes. By default, the Agent generates a 9:16, 1080P, 15-second video. If the user explicitly specifies a landscape, square, or custom duration requirement, the Agent prioritizes the requested format.

## License

This project is open-sourced. See the LICENSE file in the repository root for details.
