# Sandbox Demo - Cloud Coding Agent

**IMPORTANT**: This demo was tested with Python 3.12, but other demos here require other versions of Python. We recommend installing and managing multiple versions of Python with [mise](https://mise.jdx.dev/getting-started.html).

This is a "Cloud Coding Agent" based on BytePlus AgentKit. It showcases the **AgentKit AIO Sandbox**: a secure, isolated cloud execution environment with a shell, file system, Python/Node.js runtimes, and outbound network access.

When given a web coding task (e.g. *"build a landing page with a countdown timer"*), the agent will:

- Plan the project and scaffold it **inside the AIO Sandbox** (never on the machine the agent runs on)
- Write every source file in the sandbox using shell commands
- **Test the code inside the sandbox**: syntax checks, unit tests, and actually serving the app and verifying it with `curl`
- Zip the finished project inside the sandbox
- Upload the zip **directly from the sandbox to TOS** using a presigned URL
- Return a signed TOS download link for the completed, tested code

## Overview

### Core Features

This use case demonstrates how to build an agent around the AgentKit sandbox with the following capabilities:

- **Isolated Code Execution**: All code is written and executed in a remote AIO Sandbox session via the veadk built-in `run_code` tool, which drives the sandbox through the AgentKit `InvokeTool` API. On BytePlus, everything runs through the `RunCode` operation: a persistent IPython kernel that also executes shell commands via `!` syntax.
- **Stateful Sandbox Sessions**: Sandbox sessions persist between tool calls, so the agent can scaffold, test, fix, and package a project across many steps — and iterate on the same project in follow-up turns.
- **Real Testing, Not Claims**: The agent starts a web server inside the sandbox, curls it, and asserts on the response before declaring the task done.
- **Credential-free Artifact Delivery**: The agent runtime generates a presigned TOS PUT/GET URL pair; the sandbox pushes the zip to TOS with plain `curl -T`. Cloud credentials never enter the sandbox.
- **English by Default**: The agent plans, explains, and reports in English by default. If you write to it in another language, it switches to that language for everything you read (code identifiers, shell commands, and file names stay as they are) so its work is easy to review (see the `### Language` section in [`agent.yaml`](agent.yaml)).

The flow looks like this:

![Architecture](img/architecture.png)

<details>
<summary>Mermaid source</summary>

```mermaid
flowchart TB
    user(["User<br/>&quot;build me a web page that ...&quot;"])

    subgraph runtime["AgentKit Runtime — agent.py"]
        direction TB
        app["AgentkitAgentServerApp<br/>HTTP :8000"]
        mem[("ShortTermMemory<br/>backend = local")]

        subgraph agent["sandbox_web_coder — built by AgentBuilder from agent.yaml"]
            direction TB
            llm["deepseek-v4-pro-260425<br/>plan → scaffold → test → package → upload → report"]
            guard["pipeline_guard.py<br/>required tool: create_tos_transfer_urls<br/>completion marker: download"]
        end

        runcode["run_code — veadk builtin tool<br/>language = python3"]
        presign["create_tos_transfer_urls<br/>tool/tos_presign.py"]
    end

    subgraph sandbox["AgentKit AIO Sandbox — session per agent + user + ADK session, TTL AGENTKIT_TOOL_TTL"]
        direction TB
        kernel["Persistent IPython kernel<br/>shell via ! · files persist between calls"]
        proj["/tmp/workspace/&lt;slug&gt;/<br/>sources → py_compile / node --check<br/>→ unit tests → http.server + curl<br/>→ &lt;slug&gt;.zip"]
        kernel --> proj
    end

    ark["BytePlus ModelArk<br/>deepseek-v4-pro-260425"]
    tos[("TOS bucket<br/>DATABASE_TOS_BUCKET")]

    user -- "coding task" --> app --> llm
    app <--> mem
    llm <--> ark
    llm -- "1 · run_code(code, python3)" --> runcode
    runcode -- "AgentKit InvokeTool · RunCode<br/>AGENTKIT_TOOL_ID" --> kernel
    kernel -. "stdout / stderr as evidence" .-> llm

    llm -- "2 · filename = &lt;slug&gt;.zip" --> presign
    presign -- "pre-signed PUT + GET pair<br/>credentials stay in the runtime" --> llm
    llm -- "3 · curl -T &lt;slug&gt;.zip &lt;upload_url&gt;" --> runcode
    proj -- "PUT the zip straight from the sandbox" --> tos
    llm -- "4 · summary, file list, test output,<br/>pre-signed download link" --> user

    guard -. "injects continue_pipeline when a turn ends<br/>before the download link is delivered" .-> llm

    classDef agent fill:#e7f0ff,stroke:#3b6fd4,color:#0d1b33
    classDef tool fill:#eafaf1,stroke:#2e9e6b,color:#08281a
    classDef ext fill:#fff4e5,stroke:#d98724,color:#3a2405
    classDef store fill:#f3ecfb,stroke:#8253c6,color:#22103a
    classDef actor fill:#eceef1,stroke:#7a828c,color:#1b1f24
    class llm,guard agent
    class app,runcode,presign tool
    class kernel,proj,ark ext
    class tos,mem store
    class user actor
    style runtime fill:#fbfcfe,stroke:#9aa4b2,color:#1b1f24
    style agent fill:#f4f8ff,stroke:#3b6fd4,color:#0d1b33
    style sandbox fill:#fffaf3,stroke:#d98724,color:#3a2405
```

</details>

## Agent Capabilities

| Component | Description |
| --- | --- |
| **Agent Service** | [`agent.py`](agent.py) - Main application |
| **Auto-continue Guard** | [`pipeline_guard.py`](pipeline_guard.py) - keeps the multi-step run going in one turn: if the model ends a turn with a text-only progress note before the TOS download link has been requested and reported, the guard injects a `continue_pipeline` tool call so the user never has to type "continue" |
| **Agent Configuration** | [`agent.yaml`](agent.yaml) - Model settings, system instructions, and tool list |
| **Sandbox Execution** | `veadk.tools.builtin_tools.run_code` - Runs shell commands and code in the AIO Sandbox |
| **Custom Tools** | [`tool/tos_presign.py`](tool/tos_presign.py) - Presigned TOS upload/download URL pair generator |
| **Short-term Memory** | Session context maintenance to preserve conversational continuity |

## Quick Start

### Prerequisites

#### BytePlus Access Credentials

Make sure you have configured an IAM user, created a new Access Key / Secret Key pair, and that you have assigned the following permissions to the user:

- `AgentKitFullAccess` (AgentKit full access)
- `TOSFullAccess` (TOS full access, for presigned URL generation)

In the web console, open the product search dropdown and search for "ModelArk". Under "Model activation" make sure the following model is enabled:

- **Text:** DeepSeek V4 Pro (model ID: `deepseek-v4-pro-260425`)

**Finally, from the "API Keys" page, create a new key and save it, we'll need it later on (see *Configure Environment Variables* below).**

#### Create an AIO Sandbox Tool

The agent needs an **All-in-one (AIO) sandbox tool** in your AgentKit account. You can create one from the [BytePlus AgentKit Console](https://console.byteplus.com/agentkit/region:agentkit+ap-southeast-1/tool) (Tools → Create → AIO Sandbox), or programmatically.

After the tool is created, its tool ID (`t-...`) **must be exported as `AGENTKIT_TOOL_ID`** in the shell where you run the agent — the `run_code` tool resolves the sandbox from that variable at call time. The snippet below creates the tool and exports the variable in one step:

```bash
export BYTEPLUS_ACCESS_KEY={your_ak}
export BYTEPLUS_SECRET_KEY={your_sk}
export AGENTKIT_CLOUD_PROVIDER=byteplus

export AGENTKIT_TOOL_ID=$(uv run python - <<'EOF'
import sys
import uuid
from agentkit.sdk.tools.client import AgentkitToolsClient
from agentkit.sdk.tools import types as tt

resp = AgentkitToolsClient().create_tool(tt.CreateToolRequest(
    Name="sandbox_demo_aio",
    ToolType="All-in-one",
    Description="AIO sandbox for the sandbox_demo web coding agent",
    EnableSnapshot=True,
    AuthorizerConfiguration=tt.AuthorizerForCreateTool(
        KeyAuth=tt.AuthorizerKeyAuthForCreateTool(
            ApiKeyName=f"apikey_{uuid.uuid4().hex[:8]}",
            ApiKeyLocation="Header",
        )
    ),
))
print("Created sandbox tool:", resp.tool_id, file=sys.stderr)
# Only the tool ID goes to stdout, so the shell can capture it
print(resp.tool_id)
EOF
)
echo "AGENTKIT_TOOL_ID=$AGENTKIT_TOOL_ID"
```

`export` only affects the current shell session — when you open a new terminal, re-export the same tool ID (there is no need to create a new tool). You may want to add the `export AGENTKIT_TOOL_ID=t-...` line to your shell profile.

> **Snapshots** (`EnableSnapshot=True`): when a sandbox session's TTL expires, AgentKit takes a snapshot instead of discarding the instance; the next access to the same session transparently recreates the instance from the snapshot. For this agent that means a user can come back to a conversation hours later and the project files in `/tmp/workspace/` are still there. Snapshots can only be enabled at tool creation time — there is no update path, so if you have a non-snapshot tool you must recreate it.

> **Note**: The BytePlus AgentKit control plane currently supports only the `RunCode` operation for sandbox invocation (`ExecBash` returns `InvalidOperationType`). The agent is therefore instructed to do everything through the sandbox's persistent IPython kernel — Python code directly, shell commands via `!` syntax. The Volcano Engine copy of this demo uses `ExecBash` instead; that is the only functional difference between the two.

### Install Dependencies

*We recommend using uv to manage Python dependencies*

Once UV is installed, set up with:

```bash
uv sync
```

### Configure Environment Variables

Set the following environment variables — either export them in your shell, or copy [`.env.example`](.env.example) to `.env` (in the project directory or in the directory you launch from) and fill it in. `.env` is loaded automatically at startup (see [`consts.py`](consts.py)) and is optional; values in `.env` take precedence over variables exported in the shell, and anything missing from `.env` falls back to the shell environment. `.env` only applies to local runs — for cloud deploys pass values through `agentkit config --runtime_envs ...` (see below):

```bash
export BYTEPLUS_ACCESS_KEY={your_ak}
export BYTEPLUS_SECRET_KEY={your_sk}
export DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}
export MODEL_AGENT_API_KEY={{your_model_agent_api_key}} # Get from BytePlus ModelArk, required for local debugging
export AGENTKIT_TOOL_ID={{your_sandbox_tool_id}}        # Already set if you used the creation snippet above in this shell
export AGENTKIT_CLOUD_PROVIDER=byteplus
export CLOUD_PROVIDER=byteplus
```

**Note:** `AGENTKIT_CLOUD_PROVIDER` and `CLOUD_PROVIDER` are both **mandatory** — export them in every shell you run this sample from, and pass both through to the deployed runtime. `AGENTKIT_CLOUD_PROVIDER` is read by the agentkit SDK, while veADK reads `CLOUD_PROVIDER` — it controls veADK's default endpoints, models, and the mapping of `BYTEPLUS_*` credentials onto the `VOLCENGINE_*` variables veADK uses internally. Without them the SDKs fall back to their Volcano Engine (mainland China) defaults and calls against your BytePlus account fail. `consts.py` sets `CLOUD_PROVIDER=byteplus` as a last-resort fallback inside the agent process, but that does not cover the agentkit SDK or the tools when run standalone, so do not rely on it.

**TOS Bucket Configuration:**

- **Default bucket**: `agentkit-platform-{{your_account_id}}`
  - Where `{{your_account_id}}` needs to be replaced with your BytePlus account ID
  - Example: `DATABASE_TOS_BUCKET=agentkit-platform-12345678901234567890`
- **If you need to customize, you can modify the `bucket_name` parameter in [`tool/tos_presign.py`](tool/tos_presign.py) or pass it in during the tool call.**

## Local Execution

The simplest way to debug locally is with `veadk web`:

> `veadk web` is a web service based on FastAPI for debugging Agent applications. When you run this command, it starts a web server that loads and runs your agentkit agent code, while also providing a chat interface where you can interact with the agent. In the sidebar or a specific panel of the interface, you can view the details of the agent's execution, including the Thought Process, Tool calls, and model input/output.

Running it from within the project directory is straightforward:

```bash
uv run veadk web
```

Visit `http://localhost:8000` in your browser, select the `sandbox_demo` agent, enter a prompt, and click "Send".

### Example Prompts

- **Static page**: "Build a single-page countdown timer that counts down to New Year 2027"
- **Small game**: "Write a browser-based memory card matching game in plain HTML/CSS/JS"
- **API service**: "Write a Flask JSON API for a todo list, with unit tests"
- **Utility page**: "Build a markdown previewer web page with live rendering"
- **Follow-up iteration**: "Now add a dark mode toggle to it" (the agent reuses the same sandbox project)

**Expected Behavior:**

1. The agent restates the task and picks a project layout
2. Scaffolds and writes all files under `/tmp/workspace/<slug>/` in the AIO Sandbox
3. Runs syntax checks and tests, serves the app inside the sandbox, and curl-verifies it (you will see the real command output in the tool call results)
4. Zips the project and uploads it to TOS from inside the sandbox via a presigned URL
5. Returns a signed TOS download link, valid for 7 days

## AgentKit Deployment

### Deploy to BytePlus AgentKit Runtime

**Step 0:** If you haven't installed agentkit yet, you can do it locally (inside the Python virtual environment) with:

```bash
uv pip install agentkit-sdk-python
```

**Step 1:** Make sure you are in the current directory (`sandbox_demo`), then configure AgentKit:

**Note**: We assume here that `DATABASE_TOS_BUCKET`, `MODEL_AGENT_API_KEY`, and `AGENTKIT_TOOL_ID` are defined in your shell environment. The `agentkit` CLI does **not** read `.env` itself (only the agent process loads it at startup), so if you keep your values in `.env`, export them into your current shell first:

```bash
set -a && source ./.env && set +a
```

This also exports `BYTEPLUS_ACCESS_KEY` and `BYTEPLUS_SECRET_KEY`, which the CLI needs in order to authenticate with BytePlus during `agentkit config` and `agentkit launch`.

```bash
uv run agentkit config \
--agent_name sandbox_web_coder \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET=$DATABASE_TOS_BUCKET \
--runtime_envs MODEL_AGENT_API_KEY=$MODEL_AGENT_API_KEY \
--runtime_envs AGENTKIT_TOOL_ID=$AGENTKIT_TOOL_ID \
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
2. Click **Runtime** to view the deployed agent `sandbox_web_coder`
3. Get the public access domain name (e.g., `https://xxxxx.apigateway-ap-southeast-1.apigw-byteplus.com`) and API Key

#### Interact via the chat UI

The agent runtime includes a simple web UI (chat window) where you can interact directly with the agent.

#### Interact via the command line (CLI)

You can directly use `agentkit invoke` to trigger / debug the agent. The command is:

```bash
uv run agentkit invoke '{"prompt": "Build a single-page countdown timer that counts down to New Year 2027"}'
```

## Cleanup / Teardown

You can remove your deployed AgentKit runtime with:

```bash
uv run agentkit destroy
```

To also remove the AIO sandbox tool:

```bash
uv run agentkit sandbox delete --tool-id {{your_sandbox_tool_id}}
```

## Debugging tips

Having trouble understanding why AgentKit isn't doing what you expect? Try adding these environment variables to enable additional debug output:

```bash
export AGENTKIT_LOG_CONSOLE=true
export AGENTKIT_LOG_LEVEL=DEBUG
```

**`ValueError: The environment variable AGENTKIT_TOOL_ID not exists` when the agent calls run_code:** the shell running the agent has no `AGENTKIT_TOOL_ID` exported. Export the tool ID of your AIO sandbox tool (see *Create an AIO Sandbox Tool* above) and restart the agent.

**401 `AuthenticationError: The API key doesn't exist` on model calls:** the agent model is pinned to the BytePlus ModelArk endpoint in [`agent.yaml`](agent.yaml), so this usually means `MODEL_AGENT_API_KEY` holds a Volcano Engine Ark key (or an invalid key) rather than a BytePlus ModelArk key. Conversely, when running the *Volcano Engine* copy of this demo, make sure `CLOUD_PROVIDER`/`AGENTKIT_CLOUD_PROVIDER` are not set to `byteplus` in your shell.

## How the sandbox is used (implementation notes)

- The veadk built-in tool [`run_code`](https://github.com/volcengine/veadk-python) resolves the sandbox tool ID from `AGENTKIT_TOOL_ID` (or `AGENTKIT_TOOL_ID_SCRIPT`) and calls the AgentKit `InvokeTool` API. With `CLOUD_PROVIDER=byteplus`, the call goes to the BytePlus AgentKit endpoint (`agentkit.ap-southeast-1.bytepluses.com`). BytePlus supports the `RunCode` operation (`language: "python3"`, a persistent IPython kernel); the agent's instructions route shell commands through the kernel's `!` syntax because the `ExecBash` operation is not available on BytePlus.
- The sandbox session ID is derived from the agent name + user ID + ADK session ID, so each chat session gets its own isolated sandbox session, and files persist across tool calls within a session (session TTL is controlled by `AGENTKIT_TOOL_TTL`, default 1800s).
- The sandbox has outbound internet access but no cloud credentials. To get artifacts out, [`tool/tos_presign.py`](tool/tos_presign.py) generates a presigned PUT/GET URL pair on the agent side; the sandbox uploads with `curl -T` and the user receives the GET link.

## Known issues

- The first `run_code` call in a session may take noticeably longer than subsequent ones, since AgentKit provisions a fresh sandbox instance on demand (or restores it from a snapshot).
- Sandbox sessions expire after the TTL (default 30 minutes of inactivity, controlled by `AGENTKIT_TOOL_TTL`). With `EnableSnapshot=True` (as configured above) the session state is snapshotted on expiry and restored transparently on the next call, so project files survive. If you created the tool *without* snapshots, the files are gone after expiry and the agent must scaffold again.
