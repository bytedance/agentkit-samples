# Deploy an AgentKit target for Hi Agent

[Bidirectional sample](../README_en.md) · [中文](README.md)

## Where this agent fits

This directory implements `simple_agent`, the target on AgentKit. Hi Agent can reach it in either of two ways.

- **POC 2.** Hi Agent MCP plugin → [MCP server](../mcp_server/README_en.md) → `simple_agent` over A2A.
- **HTTP plugin alternative.** Hi Agent HTTP plugin → [HTTP adapter](../http_plugin/README_en.md) → `simple_agent` over HTTP.

Both paths can use the same target Runtime. The target generates the reply, which the server or adapter carries back to Hi Agent. The sample agent introduces itself with “我是Agentkit-01” (“I am Agentkit-01”), so you can recognize it in the Hi Agent tool result.

If you already have a compatible target Runtime, go to step 4. For MCP, the target must expose a reachable A2A service with an Agent Card and return text. Regular HTTP calls use `/invoke`. Streaming also requires the session API and `/run_sse`. For your own agent, check its introduction directly so you can recognize it later.

## 1. Install dependencies and configure the model

These commands use Python 3.12. Start at the root of the samples repository and stay in `simple_agent/` for the remaining commands.

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/simple_agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Open the API example for a model you can access in your provider’s console and set these variables in `.env`.

| Variable | Value |
| --- | --- |
| `MODEL_AGENT_NAME` | Model name or inference endpoint ID |
| `MODEL_AGENT_API_BASE` | OpenAI-compatible API base for the model. Keep the version path and omit the trailing `/chat/completions` |
| `MODEL_AGENT_API_KEY` | API key authorized to call the model |

## 2. Check the local reply and service endpoints

```bash
python veadk_agent.py
```

The script asks “请你介绍自己”. Look for “我是Agentkit-01” in the terminal output.

Start the same service entry point you will deploy.

```bash
python agent_server.py
```

In a second terminal, fetch the application list and the Agent Card.

```bash
curl -fsS http://127.0.0.1:8000/list-apps
curl -fsS http://127.0.0.1:8000/.well-known/agent-card.json
```

The list should include `simple_agent`, and the card’s `name` should also be `simple_agent`. The `a2a_caller` sample uses this name too. Check that you started the server in this directory and use the introduction above to identify the agent. Press Ctrl+C in the server terminal when finished.

## 3. Deploy and get the target Runtime’s endpoint and key

Sign in to the AgentKit CLI (`ak`) with access to a project where you can deploy a Runtime. Run `ak config -i` in `simple_agent/`.

| Setting | Value |
| --- | --- |
| Application name | Give the target a distinct name, such as `hiagent-demo-target` |
| Language, entry point, dependencies | `Python`, `agent_server.py`, `requirements.txt` |
| Deployment and authentication | `cloud`, your project and region, `key_auth` |
| Runtime environment variables | The three model variables from step 1. The image build excludes your local `.env` |

Save the configuration, then deploy from the same directory.

```bash
ak launch
```

Open the new target Runtime and send “请你介绍自己” in its online test. Once you see “我是Agentkit-01” in the reply, copy the full **endpoint** and **API key** from this Runtime’s **Quick Invocation** (快速调用) page. Keep the gateway path and `/runtime/<id>` in the endpoint. If the online test reports a model authentication error, check the three model variables configured for this Runtime.

## 4. Connect the target to Hi Agent

Use the endpoint and key from the target Runtime’s **Quick Invocation** page for the integration you choose.

- **MCP tool**. Use the target key to download the target’s Agent Card into `../mcp_server/remote_agentcard.json`. Put the same key in the MCP server’s `AGENTKIT_RUNTIME_API_KEY`. For the download command and plugin configuration, see the [MCP setup](../mcp_server/README_en.md).
- **HTTP plugin**. Set `UPSTREAM_BASE_URL` to the target endpoint and `UPSTREAM_API_KEY` to the target key in the adapter. If the target uses an application name other than `simple_agent`, set `UPSTREAM_APP_NAME` when using the session API. Follow the [HTTP plugin setup](../http_plugin/README_en.md).

If the card download returns 401, check the request header `Authorization: Bearer <target Runtime key>`.
