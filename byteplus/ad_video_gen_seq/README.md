# Ad Video Generation Agent (Sequential Multi-Agent) - E-commerce Marketing Videos

**IMPORTANT**: This demo was tested with Python 3.12, but other demos here require other versions of Python. We recommend installing and managing multiple versions of Python with [mise](https://mise.jdx.dev/getting-started.html).

This is a sequential multi-agent e-commerce marketing video generator based on BytePlus AgentKit and VeADK.

When given product information (product name, selling points, target audience, usage scenarios, and an optional product image URL), it will:

- Produce a marketing plan and generation configuration (resolution, aspect ratio, candidates per shot)
- Design a 4-shot storyboard following the AIDA marketing model (Attention → Interest → Desire → Action)
- Generate multiple candidate first-frame images per shot, then score and select the best one
- Generate multiple candidate videos per shot from the selected first frames (4–30 second clips with Dreamina Seedance 2.5), then score and select the best one
- Stitch the selected shot videos into one final video locally and upload it to TOS, returning a playable URL

## Overview

Unlike the lightweight single-agent `ad_video_gen` sample, this sample builds a full production pipeline with a `SequentialAgent`: one Root Agent orchestrates seven sub-agents in a fixed order, with candidate generation, model-based quality evaluation, video stitching, and TOS upload. Progress messages are streamed back to the user after each stage.

![Architecture](img/architecture.png)

<details>
<summary>Mermaid source</summary>

```mermaid
flowchart TB
    user(["User<br/>product brief + optional product image URL"])
    app["AgentkitAgentServerApp — main.py<br/>HTTP :8000 · also veadk web / debug.py<br/>agent.py adds the sys.path and JSON-repair patches"]

    subgraph root["root_agent — MMSequentialAgent · every stage agent runs on dola-seed-2-1-turbo-260628"]
        direction TB
        market["1 · market_agent<br/>marketing plan + generation config<br/>reads the product image · tool: web_search"]
        story["2 · storyboard_agent<br/>4-shot AIDA storyboard script"]
        image["3 · image_agent<br/>tool: image_generate<br/>N candidate first frames per shot"]
        ieval["4 · image_evaluate_agent<br/>tool: evaluate_media<br/>scores and picks one image per shot"]
        video["5 · video_agent<br/>tool: video_generate<br/>candidate clips from the winning first frame"]
        veval["6 · video_evaluate_agent<br/>tool: evaluate_media<br/>scores and picks one clip per shot"]
        release["7 · release_agent<br/>tools: video_combine · upload_file_to_tos"]
    end

    cb(["callback_agent_0..6 — interleaved after every stage<br/>streams state.cb_agent_output / cb_agent_state"])
    guard["pipeline_guard.install_by_name<br/>image · both evaluate · video · release<br/>injects continue_pipeline on an early turn end"]
    shortener["app/utils.py — UrlShortener<br/>signed media URL ⇄ compact ⌥code"]

    search["BytePlus web search API"]
    seedream["Ark · Seedream 5.0 Pro<br/>dola-seedream-5-0-pro-260628"]
    evalmodel["Ark · G-Eval vision scoring<br/>MODEL_EVALUATE_NAME · default dola-seed-2-1-turbo-260628"]
    seedance["Ark · Seedance 2.5<br/>dreamina-seedance-2-5-260628"]
    ffmpeg["Local moviepy / ffmpeg<br/>merged_videos/"]
    tos[("TOS<br/>final video · 7-day signed URL")]

    user -- "prompt" --> app --> market
    market --> story --> image --> ieval --> video --> veval --> release

    market --> search
    image --> seedream
    ieval --> evalmodel
    video --> seedance
    veval --> evalmodel
    release --> ffmpeg --> tos
    tos -- "signed URL of the final video" --> user
    cb -. "progress message after every stage" .-> user

    guard -. "stops a stage handing on an incomplete result" .-> root
    shortener -. "shortens every generated media URL and<br/>resolves it back before the next tool call" .-> root

    classDef agent fill:#e7f0ff,stroke:#3b6fd4,color:#0d1b33
    classDef tool fill:#eafaf1,stroke:#2e9e6b,color:#08281a
    classDef ext fill:#fff4e5,stroke:#d98724,color:#3a2405
    classDef store fill:#f3ecfb,stroke:#8253c6,color:#22103a
    classDef actor fill:#eceef1,stroke:#7a828c,color:#1b1f24
    class market,story,image,ieval,video,veval,release,cb agent
    class app,guard,shortener tool
    class seedream,seedance,evalmodel,search,ffmpeg ext
    class tos store
    class user actor
    style root fill:#f4f8ff,stroke:#3b6fd4,color:#0d1b33
```

</details>

Key features include:

- **Marketing planning with image understanding**: the planning agent reads the product image (URL) alongside the text brief and can use web search for platform-specific advice
- **Candidate generation and automatic evaluation**: every shot gets several candidate images/videos which are scored on aesthetics, image quality, and consistency with the reference image, so the best material is selected automatically
- **First-frame guided video generation**: each shot video is generated by Dreamina Seedance 2.5 from the winning first-frame image; clips from 4 up to 30 seconds are supported (5–10 s per shot by default)
- **Local composition and TOS upload**: the selected shot videos are stitched into one final video with moviepy and uploaded to a TOS bucket, returning a signed URL valid for 7 days
- **URL shortening for LLM safety**: long asset URLs are mapped to compact `⌥xxxxx` codes so the models never corrupt them
- **English by Default**: Every stage agent is instructed to work in English by default — marketing plan, storyboard script, image/video prompts, evaluation rationales, and replies. If your request is written in another language, the agents switch to that language for all of those outputs so the results are easy for you to review (see the `# Language` section in each stage's `prompt.py`)

## Agent Capabilities

| Component | Description |
| --- | --- |
| **Agent Module** | [`agent.py`](agent.py) - sys.path bootstrap, ADK workarounds, and the `root_agent` export for `veadk web` |
| **Auto-continue Guard** | [`pipeline_guard.py`](pipeline_guard.py) - installed on the image / evaluate / video / release sub-agents: if one of them ends its turn without calling its mandatory tool (`image_generate`, `evaluate_media`, `video_generate`, `video_combine` + `upload_file_to_tos`), the guard injects a `continue_pipeline` tool call so the stage finishes instead of handing an incomplete result to the next one |
| **Service Entry** | [`main.py`](main.py) - AgentKit service entry (`AgentkitAgentServerApp`) |
| **Debug Script** | [`debug.py`](debug.py) - runs the full pipeline once from the command line |
| **Root Orchestration** | [`app/root/`](app/root/) - `SequentialAgent` with progress-callback interleaving |
| **Marketing Planning** | [`app/market/`](app/market/) - plan, generation config, image URL detection |
| **Storyboard** | [`app/storyboard/`](app/storyboard/) - AIDA 4-shot script generation |
| **Image Generation** | [`app/image/`](app/image/) - batched candidate first-frame generation |
| **Quality Evaluation** | [`app/eval/`](app/eval/) - vision-model scoring of images and videos |
| **Video Generation** | [`app/video/`](app/video/) - batched first-frame-guided video generation |
| **Release** | [`app/release/`](app/release/) - stitching (moviepy) and TOS upload |
| **Config Example** | [`config.yaml.example`](config.yaml.example) - model names, AK/SK, and TOS bucket |
| **Cloud Provider Bootstrap** | [`consts.py`](consts.py) - sets `CLOUD_PROVIDER=byteplus` before VeADK is first imported |

## Quick Start

### Prerequisites

#### BytePlus Access Credentials

Make sure you have configured an IAM user, created a new Access Key / Secret Key pair, and that you have assigned the following permissions to the user:

- `AgentKitFullAccess` (AgentKit full access)
- `APMPlusServerFullAccess` (APMPlus full access)

In the web console, open the product search dropdown and search for "ModelArk". Under "Model activation" make sure the following models are enabled:

- **Agent / Evaluation (vision):** Seed 2.1 Turbo (model ID: `dola-seed-2-1-turbo-260628`) — this sample keeps a vision-capable agent model (rather than a text-only model such as DeepSeek V4 Pro `deepseek-v4-pro-260425` used by the single-agent `ad_video_gen` sample) because the planning agent inspects the product image and the evaluation tool scores generated images and videos
- **Images:** Seedream 5.0 Pro (model ID: `dola-seedream-5-0-pro-260628`)
- **Video:** Dreamina Seedance 2.5 (model ID: `dreamina-seedance-2-5-260628`) — supports video clips up to 30 seconds long

**Finally, from the "API Keys" page, create a new key and save it, we'll need it later on (see *Configure Environment Variables* below).**

#### TOS Bucket

The final merged video is uploaded to a TOS bucket. You can use the AgentKit platform bucket `agentkit-platform-{{your_account_id}}` (replace `{{your_account_id}}` with your BytePlus account ID) or any bucket the AK/SK pair can write to.

#### ffmpeg

Video stitching uses `moviepy`, which needs a working `ffmpeg` on the machine that runs the agent (e.g. `brew install ffmpeg` on macOS).

### Install Dependencies

*We recommend using uv to manage Python dependencies*

Once UV is installed, set up with:

```bash
uv sync
```

### Configure Environment Variables

Set the following environment variables — either export them in your shell, or copy [`.env.example`](.env.example) to `.env` (in the project directory or in the directory you launch from) and fill it in. `.env` is loaded automatically at startup (see [`consts.py`](consts.py)) and is optional; values in `.env` take precedence over variables exported in the shell, and anything missing from `.env` falls back to the shell environment. `.env` only applies to local runs — for cloud deploys pass values through `agentkit config --runtime_envs ...` (see below):

```bash
export MODEL_AGENT_API_KEY={{your_model_agent_api_key}} # Get from BytePlus ModelArk
export BYTEPLUS_ACCESS_KEY={{your_access_key}}          # For TOS upload
export BYTEPLUS_SECRET_KEY={{your_secret_key}}          # For TOS upload
export DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}
export AGENTKIT_CLOUD_PROVIDER=byteplus
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_WEB_SEARCH_API_KEY={{your_web_search_api_key}} # Get from BytePlus Searchinfinity, required by the market agent's web_search tool
```

**Note:** `AGENTKIT_CLOUD_PROVIDER` and `CLOUD_PROVIDER` are both **mandatory** — export them in every shell you run this sample from, and pass both through to the deployed runtime. `AGENTKIT_CLOUD_PROVIDER` is read by the agentkit SDK, while veADK reads `CLOUD_PROVIDER` — it controls veADK's default endpoints, models, and the mapping of `BYTEPLUS_*` credentials onto the `VOLCENGINE_*` variables veADK uses internally. Without them the SDKs fall back to their Volcano Engine (mainland China) defaults and calls against your BytePlus account fail. [`consts.py`](consts.py) sets `CLOUD_PROVIDER=byteplus` as a last-resort fallback inside the agent process, but that does not cover the agentkit SDK or the tools when run standalone, so do not rely on it.

**Note:** `BYTEPLUS_WEB_SEARCH_API_KEY` is required by the market agent's `web_search` tool when `CLOUD_PROVIDER=byteplus`. Without it, web searches fail (the pipeline keeps running, but every search returns an error). You can get an API key from the BytePlus **Searchinfinity** service — see the [Searchinfinity API Reference](https://docs.byteplus.com/en/docs/searchinfinity/Searchinfinity_API_Reference) for how to obtain and use the key.

The model names and API bases can be overridden with the following environment variables (the values below are the defaults this sample is designed for):

```bash
export MODEL_AGENT_NAME=dola-seed-2-1-turbo-260628
export MODEL_EVALUATE_NAME=dola-seed-2-1-turbo-260628
export MODEL_IMAGE_NAME=dola-seedream-5-0-pro-260628
export MODEL_VIDEO_NAME=dreamina-seedance-2-5-260628
```

Alternatively, you can copy [`config.yaml.example`](config.yaml.example) to `config.yaml` and fill in the values there — VeADK flattens the YAML keys into the same environment variables at startup (environment variables that are already set take precedence).

```bash
cp config.yaml.example config.yaml
```

## Local Execution

The simplest way to debug locally is with `veadk web`:

> `veadk web` is a web service based on FastAPI for debugging Agent applications. When you run this command, it starts a web server that loads and runs your agentkit agent code, while also providing a chat interface where you can interact with the agent. In the sidebar or a specific panel of the interface, you can view the details of the agent's execution, including the Thought Process, Tool calls, and model input/output.

Running it from within the project directory is straightforward:

```bash
uv run veadk web
```

Visit `http://localhost:8000` in your browser, select the `ad_video_gen_seq` agent, enter a prompt, and click "Send".

You can also run the full pipeline once from the command line (edit the sample prompt at the bottom of [`debug.py`](debug.py)):

```bash
uv run python debug.py
```

Or start the AgentKit API server locally on port 8000:

```bash
uv run python main.py
```

### Example Prompts

- "Please generate a Christmas marketing video for chocolate. Product name: Christmas limited dark chocolate gift box. Audience: chocolate lovers seeking festive taste, sweet sharing, and energy. Scenarios: Christmas afternoon tea, holiday gatherings, warm gift-giving. Main ingredients: selected cocoa beans, pure cocoa butter, premium milk, natural vanilla, no artificial colorants or preservatives. Flavor: melts in the mouth, silky and rich, intense cocoa aroma, slightly bitter with a sweet aftertaste. http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_chocolate.png"
- "Please generate a bread marketing video. Product name: milky soft pull-apart toast. Scenarios: breakfast pairing, afternoon tea snacks, daily meal replacement. Audience: office workers, students, families. Main ingredients: high-gluten flour, milk, eggs, butter, yeast, sugar. Features: rich milky aroma, soft crumb with even honeycomb pores, toasted crust with slightly charred spots. http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_bread.jpeg"
- "Generate an e-commerce marketing video from product images for a wabi-sabi style scented candle. Product name: wabi-sabi scented candle. Scenarios: living room decor, bedroom sleep aid, study relaxation. Audience: minimalist home decor lovers, urban professionals, fragrance collectors. Main ingredients: natural soy wax, essential oils, cement jar, paper label. Features: raw cement texture, black-and-white minimalist label, soft candlelight, reusable jar, understated and rustic. http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_candle.jpeg"

**Expected Behavior:**

1. The marketing agent analyzes the brief (and product image, if provided) and outputs a marketing plan plus generation configuration
2. The storyboard agent designs 4 AIDA shots
3. The image agent generates candidate first-frame images per shot (shown inline), and the image evaluation agent picks the best one per shot
4. The video agent generates candidate videos per shot from the selected first frames (this can take several minutes), and the video evaluation agent picks the best one per shot
5. The release agent stitches the winning shots into one final video, uploads it to TOS, and returns an HTML video preview

Note: only **one** product image URL is supported per request; the pipeline stops early and asks you to retry if more than one image is detected.

## AgentKit Deployment

### Deploy to BytePlus AgentKit Runtime

**Step 0:** If you haven't installed agentkit yet, you can do it locally (inside the Python virtual environment) with:

```bash
uv pip install agentkit-sdk-python
```

**Step 1:** Make sure you are in the current directory (`ad_video_gen_seq`), then configure AgentKit:

**Note**: We assume here that `MODEL_AGENT_API_KEY`, `BYTEPLUS_ACCESS_KEY`, `BYTEPLUS_SECRET_KEY`, and `DATABASE_TOS_BUCKET` are defined in your shell environment. The `agentkit` CLI does **not** read `.env` itself (only the agent process loads it at startup), so if you keep your values in `.env`, export them into your current shell first:

```bash
set -a && source ./.env && set +a
```

This also exports `BYTEPLUS_ACCESS_KEY` and `BYTEPLUS_SECRET_KEY`, which the CLI needs in order to authenticate with BytePlus during `agentkit config` and `agentkit launch`.

```bash
uv run agentkit config \
--agent_name ad_video_gen_seq \
--entry_point 'main.py' \
--runtime_envs MODEL_AGENT_API_KEY=$MODEL_AGENT_API_KEY \
--runtime_envs BYTEPLUS_ACCESS_KEY=$BYTEPLUS_ACCESS_KEY \
--runtime_envs BYTEPLUS_SECRET_KEY=$BYTEPLUS_SECRET_KEY \
--runtime_envs DATABASE_TOS_BUCKET=$DATABASE_TOS_BUCKET \
--runtime_envs BYTEPLUS_WEB_SEARCH_API_KEY=$BYTEPLUS_WEB_SEARCH_API_KEY \
--runtime_envs AGENTKIT_CLOUD_PROVIDER=byteplus \
--runtime_envs CLOUD_PROVIDER=byteplus \
--cloud_provider byteplus \
--launch_type cloud
```

**Note**: The `--cloud_provider byteplus` flag is required. Without it the CLI defaults to Volcano Engine, and `agentkit launch` fails with `Volcengine credentials not found (Service: sts)` while trying to resolve your account ID.

**Step 2:** Deploy the runtime:

```bash
uv run agentkit launch
```

### Test the Deployed Agent

After successful deployment:

1. Visit the [BytePlus AgentKit Console](https://console.byteplus.com/agentkit/region:agentkit+ap-southeast-1/overview?projectName=default)
2. Click **Runtime** to view the deployed agent `ad_video_gen_seq`
3. Get the public access domain name (e.g., `https://xxxxx.apigateway-ap-southeast-1.apigw-byteplus.com`) and API Key

You can directly use `agentkit invoke` to trigger / debug the agent. The command is:

```bash
uv run agentkit invoke '{"prompt": "Please generate a marketing video for a Christmas limited dark chocolate gift box, warm festive style. Product image: http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_chocolate.png"}'
```

## Cleanup / Teardown

You can remove your deployed AgentKit runtime with:

```bash
uv run agentkit destroy
```

## FAQ

### How long can the generated videos be?

Each shot is generated as a 5–10 second clip by default. Dreamina Seedance 2.5 supports clips from 4 up to 30 seconds, so you can explicitly ask for longer shots in your prompt. The final video is the concatenation of the four selected shot clips.

### Does it support direct image upload or base64 images?

Product references should be publicly accessible image URLs. Inline image data sent through the chat UI is uploaded to your TOS bucket first and then referenced by URL, which requires the TOS environment variables to be configured. At most one product image per request is supported.

### Why does the sample use Seed 2.1 Turbo instead of DeepSeek V4 Pro for the agents?

All sub-agents share one agent model, and two roles need vision: the marketing agent inspects the product image, and the evaluation tool scores generated images and videos. A text-only model cannot do this, so the sample uses the vision-capable Seed 2.1 Turbo for the agent and evaluation roles.

### Where does the final video go?

The stitched video is uploaded to the TOS bucket configured via `DATABASE_TOS_BUCKET`, and the agent returns a pre-signed URL valid for 7 days. Local intermediate files are cleaned up after the upload.
