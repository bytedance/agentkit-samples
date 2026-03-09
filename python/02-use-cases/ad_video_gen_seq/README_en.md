# E-commerce Marketing Video Generation

## Overview

> This project uses VeADK SequentialAgent (serial multi-agent orchestration) to generate e-commerce marketing videos. It builds a stable workflow by chaining “marketing planning / storyboard script / image generation / quality evaluation / video generation / final composition & publishing”. It’s suitable for quickly producing short product showcase videos (e.g., single-product promos, campaign materials).
>
> The example exposes a single Root Agent as the service entry point. Internally, multiple sub-agents execute in a fixed order, which is convenient for local debugging and cloud deployment.

- This project is derived from `04_ad_video_gen_a2a`, adapted for AgentKit platform deployment.
- This project uses sequential-agent, while the multimedia example uses A2A for agent interaction.
- This project can be deployed on the AgentKit platform.

## Key Features

This project provides the following capabilities:

- **Marketing planning & generation configuration**: based on user input (product name / selling points / asset links), generates the video structure and generation parameters
- **Storyboard script generation**: automatically outputs shot scripts, including visual description, actions, and generation highlights
- **Text-to-image / image-to-image batch generation**: generates multiple candidate first-frame images per shot, with optional reference images
- **Image/video quality evaluation & selection**: scores candidate images/videos and selects the best to reduce trial-and-error cost
- **Text-to-video / first-frame guided video generation**: generates multiple video candidates per shot based on the selected first frame
- **Local composition & TOS upload**: stitches shot videos into a final video locally, then uploads to TOS and returns an accessible URL

## Agent Capabilities

The system exposes one Root Agent and orchestrates the following sub-agents in sequence:

- **Marketing Planning Agent (`market_agent`)**: parses user inputs, fills missing key info, and generates video configuration and shot count requirements
- **Storyboard Agent (`storyboard_agent`)**: produces shot scripts based on the configuration
- **Image Agent (`image_agent`)**: batch-generates candidate first-frame images for each shot
- **Image Evaluation Agent (`image_evaluate_agent`)**: scores and selects the best image per shot
- **Video Agent (`video_agent`)**: generates shot videos from selected images (supports batch generation and multiple candidates)
- **Video Evaluation Agent (`video_evaluate_agent`)**: evaluates and selects the best shot videos
- **Release Agent (`release_agent`)**: stitches selected shot videos into a final output and uploads to TOS, returning a link

### Cost Notes

| Related Service | Description | Pricing |
| --- | --- | --- |
| [Doubao-Seed-1.6](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seed-1-6) | Understands user inputs and converts them into tool calls. | [Multiple pricing options](https://www.volcengine.com/docs/82379/1099320) |
| [Doubao-Seedance 1.5 pro](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedance-1-5-pro) | Converts images and text descriptions into videos. | [Multiple pricing options](https://www.volcengine.com/docs/82379/1099320) |
| [Doubao-Seedream 4.5 pro](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedream-4-5) | Generates images from text or reference images. | [Multiple pricing options](https://www.volcengine.com/docs/82379/1099320) |

## Run Locally

### Prerequisites

Before starting, make sure your environment meets these requirements:

- Python 3.12 or later
- veadk-python 0.5.5 (see `pyproject.toml`)
- `uv` is recommended for dependency management
- `ffmpeg` available locally (used by `moviepy` for video composition)
- <a target="_blank" href="https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey">Get Volcengine Ark API KEY</a>
- <a target="_blank" href="https://console.volcengine.com/iam/keymanage/">Get Volcengine AK/SK</a>

### Quick Start

Follow these steps to set up and run the project locally.

#### 1. Clone and install dependencies

```bash
# Clone the repository
git clone https://github.com/volcengine/agentkit-samples.git
cd agentkit-samples/python/02-use-cases/ad_video_gen_seq

# Install dependencies
uv sync --index-url https://mirrors.aliyun.com/pypi/simple

# mac or linux
source .venv/bin/activate
# windows powershell
.venv\Scripts\activate
```

#### 2. Configure environment variables

Create `config.yaml` by following `config.yaml.example`, and fill in required secrets (models, AK/SK, TOS bucket, etc.).

```bash
# Copy the config file
cp config.yaml.example config.yaml
```

Key fields in `config.yaml` include:

- `model.agent.*`: model configuration for text understanding / planning / evaluation
- `model.agent.image.*`: model configuration for image generation
- `model.agent.video.*`: model configuration for video generation
- `volcengine.access_key` / `volcengine.secret_key`: used for TOS upload authentication
- `database.tos.bucket`: bucket name used to store generated videos, images, and other artifacts
  - You can set the bucket to `agentkit-platform-{{your_account_id}}`
  - Replace `{{your_account_id}}` with your Volcengine account ID
  - Example: `DATABASE_TOS_BUCKET=agentkit-platform-12345678901234567890`

#### 3. Local debugging

- For local debugging, run `debug.py` to start the service.

  ```bash
  python debug.py
  ```

- Or debug via `veadk web`
  
  Use `veadk web` for local testing:

  ```bash
  veadk web
  ```

By default it listens on `http://0.0.0.0:8000`.

#### 4. Debugging tips

Recommended way to quickly debug the full pipeline locally:

```bash
python debug.py
```

## AgentKit Deployment

Set related environment variables before deployment:

```bash
export VOLCENGINE_ACCESS_KEY={your_ak}
export VOLCENGINE_SECRET_KEY={your_sk}
```

Deploy to runtime:

```bash
agentkit config \
    --agent_name multimedia_seq \
    --entry_point main.py \
    --launch_type cloud \
    --runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}} \
    --image_tag v1.0.0

agentkit launch
```

### Technical Details

At its core, this project is a serial multi-agent workflow built with VeADK. The Root Agent orchestrates sub-agents in a fixed sequence to form a stable, reproducible video production pipeline:

User input → Marketing planning → Storyboard generation → Image generation → Image evaluation → Video generation → Video evaluation → Composition & upload

## Directory Structure

```plaintext
/
├── README.md                 # Chinese documentation
├── README_en.md              # English documentation
├── app/                      # Agents and tool implementations
│   ├── root/                 # Root orchestration entry (SequentialAgent)
│   ├── market/               # Marketing planning (video config / shot count, etc.)
│   ├── storyboard/           # Storyboard script generation
│   ├── image/                # Image generation and result structuring
│   ├── eval/                 # Image/video evaluation and selection
│   ├── video/                # Video generation (supports batch)
│   ├── release/              # Video stitching and upload
│   └── utils.py              # URL-code mapping, TOS upload, shared utilities
├── config.yaml.example       # Example config
├── debug.py                  # Local debug script (does not start server)
├── model.py                  # Agent Model
├── main.py                   # Local service entry (AgentkitAgentServerApp)
├── pyproject.toml            # Dependency management (uv)
└── requirements.txt          # Dependency management (pip/uv pip)
```

## Example Prompts

Here are some commonly used prompt examples:

- `Please generate a Christmas marketing video for chocolate. Product name: Christmas limited dark chocolate gift box. Applicable scenarios and audience: suitable for all chocolate lovers, especially consumers seeking the ultimate Christmas taste, sweet sharing, and energy replenishment; suitable for Christmas afternoon tea, holiday gatherings with friends and family, warm gift-giving, or any moment that needs a festive atmosphere. Main ingredients: selected cocoa beans, pure cocoa butter, premium milk, natural vanilla, no artificial colorants or preservatives, rich in antioxidants. Flavor/features: melts in the mouth, silky and rich, intense cocoa aroma, slightly bitter with a sweet aftertaste and a warm holiday-limited finish http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_chocolate.png`
- `Please generate a bread marketing video. Product name: milky soft pull-apart toast. Scenarios/audience: scenarios: breakfast pairing, afternoon tea snacks, daily meal replacement; audience: office workers, students, families (bread lovers who prefer soft texture). Main ingredients: high-gluten flour, milk, eggs, butter, yeast, sugar. Flavor/features: rich milky aroma; tastes sweet and smooth when paired with butter + honey; features: soft crumb with even honeycomb pores, toasted crust with slightly charred spots, combining a soft interior and a crispy crust http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_bread.jpeg`
- `Generate an e-commerce marketing video from product images for a wabi-sabi style scented candle. Product name: wabi-sabi scented candle. Scenarios/audience: scenarios: living room decor, bedroom sleep aid, study relaxation, minimalist ambience; audience: home decor lovers who like minimalism / wabi-sabi aesthetics, urban professionals seeking a relaxed vibe, fragrance collectors. Main ingredients: natural soy wax, essential oils, cement jar, paper label sticker. Scents/features: wood scents (cedar/sandalwood) or herbal scents (sage/eucalyptus), etc.; features: cement jar with raw texture, black-and-white minimalist patterned label; soft candlelight; jar reusable; overall understated and rustic, matching wabi-sabi aesthetics http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_candle.jpeg`

## Demo Output

The system can:

- ✅ Automatically parse product information and generate marketing strategy
- ✅ Create high-quality video scripts and storyboards
- ✅ Generate engaging marketing copy
- ✅ Produce professional e-commerce marketing videos
- ✅ Provide video quality evaluation and optimization
- ✅ Support one-click publishing to multiple platforms

## FAQ

FAQ list to be added.

## License

This project is open-sourced. See the LICENSE file in the repository root for details.

