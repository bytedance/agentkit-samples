# Comic Drama Generator

**IMPORTANT**: This demo works with Python 3.12 but *not* Python 3.14. You can use a tool such as [mise](https://mise.jdx.dev/getting-started.html) to install and manage multiple Python versions.

An AI-powered comic drama production Agent built on BytePlus AgentKit. Simply input a story idea, and the agent will automatically complete the entire pipeline — from screenplay writing, character design, storyboard generation, scene video generation, to final video compositing — delivering a complete comic drama video with a TOS download link.

## Core Features

- **End-to-End Automation**: 8-step pipeline from creative concept to finished film, no manual intervention required
- **Intelligent Duration Allocation**: Dynamic 4~30 second allocation per scene for natural pacing
- **Professional Camera Language**: Built-in director-level camera strategies (speed ramps, 360° orbits, tracking shots, etc.)
- **Content Safety Pre-screening**: Automatic risk assessment with proactive handling of sensitive content
- **Style Consistency**: STYLE_ANCHOR maintained throughout the entire workflow with strict character prompt reuse
- **English by Default**: The agent works in English by default — its replies, the generated documents, the image and video prompts, and the dialogue the characters speak on screen. If you write to it in another language, it switches to that language for all of those outputs (and the characters speak it) so the results are easy for you to review
- **Output Verification**: Automatic file integrity checks + AI quality scoring after each step
- **Multi-Genre Support**: Mythology, martial arts, cultivation, urban, sci-fi, children's stories, and 10+ more genres
- **MCP Tool Integration**: Video editing capability via `@pickstar-2002/video-clip-mcp`
- **Checkpoint Resume**: Interrupted tasks can be resumed from the last completed step
- **Runs Unattended**: The pipeline runs from story idea to final video in a single turn. If the model ever ends a turn between steps (a text-only "moving on to Step N" reply, which would otherwise stop the run and force you to type "continue"), the runtime guard in `pipeline_guard.py` injects a `continue_pipeline` tool call so the run resumes on its own
- **Parallel Image Generation**: Character portraits and storyboard images support parallel generation for significantly improved efficiency
- **Auto-Retry on Failure**: Automatic retry on scene generation failures for higher success rates

## Production Pipeline

![Production pipeline](img/production_pipeline.png)

<details>
<summary>Mermaid source</summary>

```mermaid
flowchart TB
    idea(["User story idea"])

    s0["Step 0 · Resume detection<br/>task_manager.py list"]
    s1["Step 1 · Load configuration<br/>app_config.py · VIDEO_DURATION_MINUTES<br/>smart duration mode, 4-30 s per scene"]
    s2["Step 2 · Initialize task directory<br/>task_manager.py init"]
    safety{{"Content-safety pre-review<br/>low / medium / high risk"}}
    s3["Step 3 · Screenplay<br/>web_search.py research<br/>+ smart duration allocation"]
    s4["Step 4 · Character design<br/>batch_image_generate.py — parallel portraits"]
    s5["Step 5 · Scene art<br/>batch_image_generate.py — storyboard frames<br/>STYLE_ANCHOR + character prompt reuse"]
    s6["Step 6 · Scene videos<br/>batch_video.py submit → poll<br/>per-scene duration · auto-retry on failure"]
    s7["Step 7 · Synthesis and delivery<br/>file_download.py → video_merge.py (ffmpeg)<br/>→ tos_upload.py"]
    s8["Step 8 · Artifact verification + scoring<br/>verify_task.py · video_scorer.py"]

    art[("Task directory<br/>requirements.md · plot.md · script.md<br/>characters.md + characters/<br/>storyboard/ · videos/ · final_video.mp4")]
    tos[("TOS · signed download URL")]
    done(["Final video + TOS link + scoring report<br/>ending with the Pipeline complete line"])

    idea --> s0 --> s1 --> s2 --> safety
    safety -- "medium: euphemistic rewrites<br/>high: warn the user first" --> s3
    s3 --> s4 --> s5 --> s6 --> s7 --> s8 --> done
    s0 -. "unfinished task found: resume from the last completed step" .-> s6

    s3 --> art
    s4 --> art
    s5 --> art
    s6 --> art
    s7 --> art
    art --> s8
    s7 --> tos --> done

    classDef agent fill:#e7f0ff,stroke:#3b6fd4,color:#0d1b33
    classDef tool fill:#eafaf1,stroke:#2e9e6b,color:#08281a
    classDef ext fill:#fff4e5,stroke:#d98724,color:#3a2405
    classDef store fill:#f3ecfb,stroke:#8253c6,color:#22103a
    classDef actor fill:#eceef1,stroke:#7a828c,color:#1b1f24
    class s0,s1,s2,s3,s4,s5,s6,s7,s8 tool
    class safety ext
    class art,tos store
    class idea,done actor
```

</details>

## System Architecture

![System architecture](img/system_architecture.png)

<details>
<summary>Mermaid source</summary>

```mermaid
flowchart TB
    user(["User<br/>story idea · or &quot;continue&quot; to resume a task"])

    subgraph runtime["AgentKit Runtime — agent.py"]
        direction TB
        app["AgentkitAgentServerApp<br/>HTTP :8000"]
        mem[("ShortTermMemory<br/>sqlite · .data/sessions.db")]

        subgraph agent["comic_drama_master — built by AgentBuilder from agent.yaml"]
            direction TB
            llm["deepseek-v4-pro-260425<br/>content-safety pre-review · 8-step orchestration"]
            guard["pipeline_guard.py<br/>completion markers: pipeline complete ·<br/>artifact verification report · overall score"]
            registry["url_registry.py<br/>restores pre-signed URLs in tool arguments"]
        end

        skills["SkillsToolset (skills_mode = local)<br/>skills · bash · read_file · write_file · edit_file"]
        mcp["McpToolset — stdio<br/>@pickstar-2002/video-clip-mcp"]
    end

    subgraph skill["skill/comic-drama-master — loaded on demand by the skills tool"]
        direction TB
        skillmd["SKILL.md — Steps 0-8 + camera-language guide<br/>references/: screenplay · character · scene ·<br/>storyboard · video-synthesizer"]
        scripts["scripts/ run through bash:<br/>app_config · task_manager · web_search<br/>image_generate · batch_image_generate<br/>batch_video submit/poll · file_download<br/>video_merge · tos_upload · video_scorer · verify_task"]
        skillmd --> scripts
    end

    subgraph ark["BytePlus ModelArk — called directly over HTTPS by the scripts"]
        direction TB
        seedream["Seedream 5.0 Pro<br/>dola-seedream-5-0-pro-260628<br/>character portraits + storyboard frames"]
        seedance["Seedance 2.5<br/>dreamina-seedance-2-5-260628<br/>one clip per scene, 4-30 s each"]
        scorer["Vision model — video_scorer.py<br/>quality score per artifact"]
    end

    search["BytePlus web search API<br/>background research for the screenplay"]
    outdir[("COMIC_DRAMA_OUTPUT_DIR/task_&lt;timestamp&gt;_&lt;name&gt;/<br/>plot.md · script.md · characters/ · storyboard/<br/>videos/ · final_video.mp4")]
    tos[("TOS<br/>final video · signed download URL")]

    user -- "story idea" --> app --> llm
    app <--> mem
    llm --> skills --> skillmd
    llm -- "bash: python scripts/..." --> scripts
    scripts --> seedream
    scripts --> seedance
    scripts --> scorer
    scripts --> search
    scripts <--> outdir
    scripts -- "video_merge.py (ffmpeg) → tos_upload.py" --> tos
    llm -. "optional clip editing" .-> mcp
    tos -- "signed URL + verification report" --> user

    guard -. "injects continue_pipeline until Step 8<br/>reports the final Pipeline complete line" .-> llm
    registry -. "keeps signed image / video URLs intact" .-> scripts

    classDef agent fill:#e7f0ff,stroke:#3b6fd4,color:#0d1b33
    classDef tool fill:#eafaf1,stroke:#2e9e6b,color:#08281a
    classDef ext fill:#fff4e5,stroke:#d98724,color:#3a2405
    classDef store fill:#f3ecfb,stroke:#8253c6,color:#22103a
    classDef actor fill:#eceef1,stroke:#7a828c,color:#1b1f24
    class llm,guard,registry agent
    class app,skills,mcp,skillmd,scripts tool
    class seedream,seedance,scorer,search ext
    class tos,mem,outdir store
    class user actor
    style runtime fill:#fbfcfe,stroke:#9aa4b2,color:#1b1f24
    style agent fill:#f4f8ff,stroke:#3b6fd4,color:#0d1b33
    style skill fill:#f2fbf6,stroke:#2e9e6b,color:#08281a
    style ark fill:#fffaf3,stroke:#d98724,color:#3a2405
```

</details>

## Quick Start

### Prerequisites

#### BytePlus Access Credentials

1. Log in to the [BytePlus Console](https://console.byteplus.com)
2. Go to "Identity and Access Management" → "Users" → Create a new user or search for an existing username → Click the username to enter "User Details" → Go to "Keys" → Create a new key or copy an existing AK/SK
3. Configure access permissions for the services that AgentKit depends on for the user:
    - On the "User Details" page → Go to "Permissions" → Click "Add Permission", and grant the following policies to the user
    - `AgentKitFullAccess` (AgentKit full access)
    - `APMPlusServerFullAccess` (APMPlus full access)
4. Obtain the ModelArk API key for the user
    - Search for the "ModelArk" product and click to enter the console
    - Go to "API Key Management" → Create or copy an existing API Key
5. Activate the following pre-built inference endpoints ("Model activation" in the ModelArk console):
   - Agent model: `deepseek-v4-pro-260425`
   - Image generation model: `dola-seedream-5-0-pro-260628` (listed under "Dola-Seedream-5.0-pro")
   - Video generation model: `dreamina-seedance-2-5-260628` (listed under "Dreamina-Seedance-2.5") — supports video clips up to 30 seconds long

#### Node.js Environment

- Install Node.js 18+ and npm ([Node.js Installation](https://nodejs.org/en))
- Ensure the `npx` command is available in the terminal
- The MCP video tool (`@pickstar-2002/video-clip-mcp`) will be automatically started via `npx` when the agent is running — no manual installation required

#### ffmpeg

Video merging (Step 7 of the pipeline) uses `ffmpeg` / `ffprobe`. Install it with your package manager, e.g.:

```bash
# macOS
brew install ffmpeg
# Debian/Ubuntu
sudo apt-get install -y ffmpeg
```

#### TOS Storage Bucket

Create a TOS storage bucket for storing generated images and video files in the [BytePlus TOS Console](https://console.byteplus.com/tos). The default AgentKit bucket name has the form `agentkit-platform-{{your_account_id}}`.

### Install Dependencies

*We recommend using uv to manage Python dependencies*

Once uv is installed, set up with:

```bash
uv sync
```

If you are in China and have connectivity issues, you can use this command instead:

```bash
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Configure Environment Variables

Two methods are supported:

#### Method 1: `.env` File (Recommended)

Copy [`.env.example`](.env.example) to `.env` in the `comic_drama_gen/` directory (or in the directory you launch from) and fill in the values:

```bash
BYTEPLUS_ACCESS_KEY=your_ak
BYTEPLUS_SECRET_KEY=your_sk
MODEL_AGENT_API_KEY=your_ark_api_key
DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}
AGENTKIT_CLOUD_PROVIDER=byteplus
CLOUD_PROVIDER=byteplus

# Optional
COMIC_DRAMA_OUTPUT_DIR=./my-comic-drama
VIDEO_DURATION_MINUTES=0.5
DEFAULT_VIDEO_MODEL_NAME=dreamina-seedance-2-5-260628
```

> The `.env` file is loaded automatically at startup (via `python-dotenv`). Values in `.env` take precedence over variables exported in the shell; anything missing from `.env` falls back to the shell environment. The file is optional — if it does not exist, only the shell environment is used. `consts.py` looks for `.env` in the project directory first and then in the current working directory (the project-directory file wins for keys present in both).

#### Method 2: Direct Export

```bash
# Required
export BYTEPLUS_ACCESS_KEY=your_ak
export BYTEPLUS_SECRET_KEY=your_sk
export MODEL_AGENT_API_KEY=your_ark_api_key
export AGENTKIT_CLOUD_PROVIDER=byteplus
export CLOUD_PROVIDER=byteplus

# TOS bucket (for uploading generated videos)
export DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}

# Optional
export COMIC_DRAMA_OUTPUT_DIR=./my-comic-drama
export VIDEO_DURATION_MINUTES=0.5
export DEFAULT_VIDEO_MODEL_NAME=dreamina-seedance-2-5-260628
```

**Note:** `AGENTKIT_CLOUD_PROVIDER` and `CLOUD_PROVIDER` are both **mandatory** — set them in your `.env` file or export them in every shell you run this sample from, and pass both through to the deployed runtime. `AGENTKIT_CLOUD_PROVIDER` is read by the agentkit SDK, while veADK reads `CLOUD_PROVIDER` — it controls veADK's default endpoints, models, and the mapping of `BYTEPLUS_*` credentials onto the `VOLCENGINE_*` variables veADK uses internally. Without them the SDKs fall back to their Volcano Engine (mainland China) defaults and calls against your BytePlus account fail. `consts.py` sets `CLOUD_PROVIDER=byteplus` as a last-resort fallback inside the agent process, but that does not cover the agentkit SDK or the skill scripts when run standalone, so do not rely on it.

**Environment Variables Reference:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BYTEPLUS_ACCESS_KEY` | ✅ | — | BytePlus access key |
| `BYTEPLUS_SECRET_KEY` | ✅ | — | BytePlus secret key |
| `AGENTKIT_CLOUD_PROVIDER` | ✅ | — | Points the agentkit SDK at BytePlus |
| `CLOUD_PROVIDER` | ✅ | — | Points veADK's default endpoints and models at BytePlus (`consts.py` falls back to `byteplus`, but export it anyway) |
| `MODEL_AGENT_API_KEY` | ✅ | — | ModelArk API key (`ARK_API_KEY` also works — whichever is set is mirrored to the other) |
| `DATABASE_TOS_BUCKET` | ✅ | — | TOS bucket name |
| `COMIC_DRAMA_OUTPUT_DIR` | ❌ | `output/` under project dir | Output root directory |
| `VIDEO_DURATION_MINUTES` | ❌ | `0.5` | Video duration in minutes, supports 0.5/1/2/3/4 (0.5 = 30s) |
| `DEFAULT_VIDEO_MODEL_NAME` | ❌ | `dreamina-seedance-2-5-260628` | Video generation model name |

## Local Execution

### Method 1: Use veadk web (Recommended for Debugging)

> `veadk web` is a web service based on FastAPI for debugging Agent applications. It starts a web server that loads and runs your agent code, and provides a chat interface where you can interact with the agent and inspect its thought process, tool calls, and model input/output.

Run it from within the project directory (`comic_drama_gen`):

```bash
uv run veadk web
```

Open `http://localhost:8000` in your browser, select the `comic_drama_gen` agent, enter your story idea, and send.

### Method 2: Direct API Call

```bash
uv run agent.py
# Service listens on 0.0.0.0:8000 by default
```

**Create a session:**
```bash
curl -X POST 'http://localhost:8000/apps/comic_drama_master/users/u_123/sessions/s_1' \
  -H 'Content-Type: application/json'
```

**Send a message:**
```bash
curl 'http://localhost:8000/run_sse' \
  -H 'Content-Type: application/json' \
  -d '{
    "appName": "comic_drama_master",
    "userId": "u_123",
    "sessionId": "s_1",
    "newMessage": {
      "role": "user",
      "parts": [{"text": "Sun Wukong battles Erlang Shen, Chinese anime 3D realistic style"}]
    },
    "streaming": true
  }'
```

### Example Prompts

| Genre | Example Prompt |
|-------|---------------|
| Chinese Mythology | `Sun Wukong battles Erlang Shen, Chinese anime 3D realistic style` |
| Martial Arts | `Legend of the Condor Heroes, Guo Jing vs Ouyang Feng, live-action version` |
| Cultivation | `Han Li forming his Nascent Soul in A Record of a Mortal's Journey to Immortality, 2 min video` |
| Historical | `Jing Ke's last night before assassinating the King of Qin` |
| Urban | `Office Showdown: Intern's rise to tech CEO, Japanese anime 2D style` |
| Sci-Fi | `Interstellar agents saving Earth` |
| Children's | `Little fox searching for star fragments` |

## Directory Structure

```
comic_drama_gen/
├── agent.py                # Agent entry (MCP tool registration, skill loading, session storage)
├── agent.yaml              # Agent configuration (model, system instructions)
├── consts.py               # Default constants + .env auto-loading
├── pipeline_guard.py       # Auto-continue guard: keeps the 8-step run going if the model ends a turn between steps
├── url_registry.py         # Signed-URL registry: restores TOS signed URLs the model truncated
├── .env.example            # Environment variable template (copy to .env)
├── .env                    # Environment variable config file (create from .env.example)
├── pyproject.toml          # Python project configuration
├── requirements.txt        # Dependency list
├── scripts/                # Helper scripts directory
│   └── setup.sh            # Cloud deployment build script (pre-installs video-clip-mcp)
├── img/                    # Image assets for README
└── skill/comic-drama-master/
    ├── SKILL.md             # Master director skill spec (8-step full pipeline)
    ├── examples/
    │   └── examples.md      # Complete usage examples
    ├── references/
    │   ├── character-designer.md     # Character design specification
    │   ├── scene-designer.md         # Scene art specification
    │   ├── screenplay-generator.md   # Screenplay generation specification
    │   ├── storyboard-director.md    # Storyboard direction specification
    │   └── video-synthesizer.md      # Video synthesis specification
    └── scripts/
        ├── app_config.py         # Video duration config reader
        ├── task_manager.py       # Task directory management (FIFO cleanup, max 16 tasks)
        ├── batch_video.py        # Batch video task submit/poll
        ├── batch_image_generate.py  # Batch parallel image generation
        ├── create_video_task.py  # Single video task creation
        ├── query_video_task.py   # Video task status query
        ├── image_generate.py     # Image generation (base64 direct save)
        ├── web_search.py         # Web search (for screenplay research)
        ├── video_merge.py        # ffmpeg video merging
        ├── video_scorer.py       # AI quality scoring (5 dimensions)
        ├── verify_task.py        # Output integrity verification
        ├── tos_upload.py         # TOS upload
        ├── file_download.py      # Batch file download
        └── get_aksk.py           # AK/SK credential retrieval
```

## Output Directory Structure

After each task completes, the `COMIC_DRAMA_OUTPUT_DIR` (defaults to `output/` under the project directory) will contain:

```
{COMIC_DRAMA_OUTPUT_DIR}/
└── task_20260222_143000_sun_wukong_battle/
    ├── requirements.md   # Requirements document (with web_search research summary)
    ├── plot.md           # Chapter-based plot outline (with smart duration allocation)
    ├── script.md         # Complete dialogue script (with per-second timestamps + per-chapter duration)
    ├── characters.md     # Character design (STYLE_ANCHOR + character prompts + portrait images)
    ├── cover.jpg         # Cover image
    ├── cover.md          # Cover information
    ├── final_video.md    # Final delivery document (with TOS link)
    ├── storyboard/       # Storyboards (scene_01.jpg ~ scene_NN.jpg)
    ├── characters/       # Character portraits (char_*.jpg)
    ├── videos/           # Scene videos (scene_01.mp4 ~ scene_NN.mp4, smart duration 4~30s)
    └── final/            # Composited drama (*_final.mp4)
```

## AgentKit Deployment

### Deploy to BytePlus AgentKit Runtime

**Step 0:** If you haven't installed agentkit yet, you can do it locally (inside the Python virtual environment) with:

```bash
uv pip install agentkit-sdk-python
```

**Step 1:** Make sure you are in the current directory (`comic_drama_gen`), then configure AgentKit:

**Note**: We assume here that `DATABASE_TOS_BUCKET` and `MODEL_AGENT_API_KEY` are defined in your environment. The `agentkit` CLI does **not** read `.env` itself (only the agent process loads it at startup), so if you keep your values in `.env`, export them into your current shell first:

```bash
set -a && source ./.env && set +a
```

This also exports `BYTEPLUS_ACCESS_KEY` and `BYTEPLUS_SECRET_KEY`, which the CLI needs in order to authenticate with BytePlus during `agentkit config` and `agentkit launch`.

```bash
uv run agentkit config \
  --agent_name comic_drama_master \
  --entry_point 'agent.py' \
  --runtime_envs DATABASE_TOS_BUCKET=$DATABASE_TOS_BUCKET \
  --runtime_envs MODEL_AGENT_API_KEY=$MODEL_AGENT_API_KEY \
  --runtime_envs AGENTKIT_CLOUD_PROVIDER=byteplus \
  --runtime_envs CLOUD_PROVIDER=byteplus \
  --cloud_provider byteplus \
  --launch_type cloud
```

**Note**: The `--cloud_provider byteplus` flag is required. Without it the CLI defaults to Volcano Engine, and `agentkit launch` fails with `Volcengine credentials not found (Service: sts)` while trying to resolve your account ID.

> **Important**: Environment variables exported in your shell are **not** uploaded to the cloud runtime automatically — only the `runtime_envs` entries in `agentkit.yaml` (plus the contents of a local `.env` file, which the deploy step merges in) reach the deployed runtime. If `MODEL_AGENT_API_KEY` is missing from `runtime_envs`, the deployed agent has no ModelArk API key and every image/video generation call fails with a 401. The `agent.py` startup mirrors `MODEL_AGENT_API_KEY` to `ARK_API_KEY`, so this single variable covers the LLM, image, and video calls.

**Step 2:** Modify the `agentkit.yaml` deployment configuration

> Purpose: After modification, it will pre-install video-clip-mcp during the image build phase to accelerate runtime startup.

```bash
# On Linux
sed -i 's/docker_build: {}/docker_build:\n  build_script: "scripts\/setup.sh"/' agentkit.yaml

# On macOS
sed -i '' 's/docker_build: {}/docker_build:/' agentkit.yaml && sed -i '' '/docker_build:/a\
  build_script: "scripts\/setup.sh"' agentkit.yaml
```

**Step 3:** Deploy the runtime:

```bash
uv run agentkit launch
```

### Test the Deployed Agent

After successful deployment:

1. Visit the [BytePlus AgentKit Console](https://console.byteplus.com/agentkit/region:agentkit+ap-southeast-1/overview?projectName=default)
2. Click **Runtime** to view the deployed agent `comic_drama_master`
3. Obtain the public access domain and API Key to call via API

#### Page-Based Debugging

The AgentKit agent list page provides a debugging entry point. Click it to debug the agent's features through a visual UI.

![Agent Page Debug 1](./img/agent-test-run-01.png)

![Agent Page Debug 2](./img/agent-test-run-02.png)

#### Command-Line Debugging

Use `agentkit invoke` to initiate debugging directly:

```bash
uv run agentkit invoke '{"prompt": "Sun Wukong battles Erlang Shen, Chinese anime 3D realistic style"}'
```

#### API-Based Debugging

**Create a session:**

```bash
curl --location --request POST 'https://xxxxx.apigateway-ap-southeast-1.apigw-byteplus.com/apps/comic_drama_master/users/u_123/sessions/s_124' \
--header 'Content-Type: application/json' \
--header 'Authorization: <your_api_key>' \
--data ''
```

**Send a message:**

```bash
curl --location 'https://xxxxx.apigateway-ap-southeast-1.apigw-byteplus.com/run_sse' \
--header 'Authorization: <your_api_key>' \
--header 'Content-Type: application/json' \
--data '{
    "appName": "comic_drama_master",
    "userId": "u_123",
    "sessionId": "s_124",
    "newMessage": {
        "role": "user",
        "parts": [{
            "text": "Sun Wukong battles Erlang Shen, Chinese anime 3D realistic style"
        }]
    },
    "streaming": true
}'
```

## Cleanup / Teardown

You can remove your deployed AgentKit runtime with:

```bash
uv run agentkit destroy
```

## FAQ

**Video generation task failed (`OutputVideoSensitiveContentDetected`):**
- When the subject contains martial arts/war/violence elements, the Agent will automatically use euphemistic alternatives
- If it repeatedly fails, explicitly request "use gentle expressions" in your prompt

**`uv sync` failed:**
- Ensure Python 3.12+ is installed
- Try using a mirror: `uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple --refresh`

**TOS upload failed:**
- Confirm that `BYTEPLUS_ACCESS_KEY`, `BYTEPLUS_SECRET_KEY`, and `DATABASE_TOS_BUCKET` are all correctly set
- Verify that the account has TOS bucket read/write permissions

**Too many task directories:**
- `task_manager.py` automatically retains the latest 16 tasks (FIFO cleanup policy)
- Use the `COMIC_DRAMA_OUTPUT_DIR` environment variable to separate test and production outputs

**`.env` file not taking effect:**
- Confirm the `.env` file is located in the `comic_drama_gen/` directory or in the directory you launch from
- `.env` values override variables set via `export`; if a value looks wrong, check for a stale entry in `.env`
- `python-dotenv` is a pinned dependency; re-run `uv sync` / `pip install -r requirements.txt` if the import fails

**`npx` command not found:**
- Install Node.js 18+ and npm
- Verify that `npx --version` runs correctly in the terminal

**MCP tool connection error:**
- Ensure the default MCP port does not conflict
- Check the Node.js process logs for detailed error messages

## Related Resources

- [BytePlus AgentKit](https://docs.byteplus.com/en/docs/agentkit)
- [BytePlus TOS Object Storage](https://www.byteplus.com/en/product/TOS)
- [BytePlus AgentKit Console](https://console.byteplus.com/agentkit/region:agentkit+ap-southeast-1/overview?projectName=default)

## Code License

This project is licensed under the Apache 2.0 License

## Known issues

- Video style is not always consistent across the entire video because reference images are generated independently, which can lead to stylistic differences.
- Image and video generation will sometimes time out forcing a re-try


