# Call an AgentKit agent from Hi Agent using MCP

[Bidirectional sample](../README_en.md) · [中文](README.md)

## Call flow

**Hi Agent assistant → Hi Agent MCP plugin → MCP server (this directory) → target agent on AgentKit over A2A**

This directory implements the MCP server for POC 2. The server and the target agent run on separate AgentKit Runtimes. The Hi Agent MCP plugin connects to this server to discover and call `remote_agent_poc_hiagent(message)`. For each call, the tool starts a new session, sends the message to the target over A2A, and returns the final text to Hi Agent.

When registering an A2A service directly, the Hi Agent version used in this sample could not set the authentication header required to fetch the target’s Agent Card. With the MCP plugin, the server reads the card downloaded during setup and uses the target Runtime’s key to make the A2A call.

## 1. Prepare a target Runtime

Use the sample target or an existing AgentKit Runtime. The target must expose a reachable A2A service with an Agent Card and return text. First ask the agent to introduce itself in the target Runtime’s online test. Pick out a phrase you can recognize later. The sample target uses “我是Agentkit-01” (“I am Agentkit-01”). [Deploy the sample target](../simple_agent/README_en.md)

Copy the full endpoint and API key from the target Runtime’s **Quick Invocation** (快速调用) page. You will use two different keys.

| Call | Key to use | Where it goes |
| --- | --- | --- |
| MCP server → target agent | Target Runtime key | `AGENTKIT_RUNTIME_API_KEY` on the MCP server |
| Hi Agent → MCP server | MCP server Runtime key from step 4 | `Authorization` header in the Hi Agent plugin |

## 2. Download the target agent’s card

These commands use Python 3.12. Start at the root of the samples repository and stay in `mcp_server/` for the remaining steps.

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/mcp_server
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

In `.env`, set `AGENTKIT_RUNTIME_API_KEY` to the target Runtime key. Enter just the key. Set `SIMPLE_AGENT_ENDPOINT` below to the target’s full endpoint and download the Agent Card. Sourcing `.env` makes the key available in the current shell.

```bash
SIMPLE_AGENT_ENDPOINT='https://<gateway-host>/runtime/<target-runtime-id>'
source .env
curl -fsS -H "Authorization: Bearer ${AGENTKIT_RUNTIME_API_KEY}" \
  "${SIMPLE_AGENT_ENDPOINT%/}/.well-known/agent-card.json" -o remote_agentcard.json
```

Open `remote_agentcard.json` and check that the `url` points to the target Runtime and is reachable from the MCP server. If the sample target’s unsigned card lists `http://localhost:8000/`, replace it with the full target endpoint followed by `/`. Keep `/runtime/<id>` in the path and update matching local addresses in `additionalInterfaces`. For a signed card, ask the publisher to update it.

## 3. Call the tool locally

Start the MCP server.

```bash
python mcp_server.py
```

In a second terminal, send a `tools/call` request to the local `/mcp` endpoint. The tool sends `message` to the agent named in the card.

```bash
curl -fsS http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"remote_agent_poc_hiagent","arguments":{"message":"请介绍你自己"}}}'
```

Check `result.content` in the response. With the sample target, look for “我是Agentkit-01”. With your own target, look for the introduction you checked in step 1. To check tool discovery alone, change the `-d` value to `'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`. Listing tools only verifies the connection to the MCP server.

## 4. Deploy the MCP server

Sign in to the AgentKit CLI (`ak`) with access to a project where you can deploy a Runtime. Run `ak config -i` in `mcp_server/`.

| Setting | Value |
| --- | --- |
| Application name | Give the MCP server a name distinct from the target Runtime |
| Language, entry point, dependencies | `Python`, `mcp_server.py`, `requirements.txt` |
| Deployment and authentication | `cloud`, your project and region, `key_auth` |
| Runtime environment variables | Set `AGENTKIT_RUNTIME_API_KEY` to the **target Runtime key** |

Keep `remote_agentcard.json` in this directory. The Dockerfile copies the card into the image. Your local `.env` is for local testing. Once configured, deploy.

```bash
ak launch
```

Open **Quick Invocation** for the new **MCP server Runtime**. Copy its own endpoint and API key for Hi Agent.

## 5. Add and verify the tool in Hi Agent

1. Create an **MCP plugin**. Choose **Streamable HTTP** as the MCP transport and set the URL to `<MCP server endpoint>/mcp`.
2. Select **API Key** authentication and **Header** as its location. Use `Authorization` as the name and `Bearer <MCP server Runtime key>` as the value.
3. Select **Sync tools** and look for `remote_agent_poc_hiagent`. Publish the plugin and add the tool to your agent in Hi Agent.
4. In the chat, ask “Call remote_agent_poc_hiagent and ask the remote agent to introduce itself.” Open the tool trace, check the tool name, and compare the introduction in the result with the one from step 1.

If tool discovery returns 401, check the MCP server key in the plugin. If discovery succeeds but the target rejects the tool call, check the target Runtime key in the MCP server’s environment.
