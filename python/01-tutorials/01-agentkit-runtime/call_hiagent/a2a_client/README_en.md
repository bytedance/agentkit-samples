# Call Hi Agent from AgentKit with an A2A Client

[中文](README.md) · [Back to the integration sample](../README_en.md)

## Call flow

**External caller → service on AgentKit Runtime (this directory) → A2A Client → Hi Agent assistant**

This directory implements POC 1.1. An external caller sends an HTTP or JSON-RPC request to the Runtime. The service calls Hi Agent directly over A2A and returns the remote result. Hi Agent generates the reply; this service needs no model configuration.

The code has two files: [a2a_server.py](a2a_server.py) exposes the endpoints, and [a2a_tool.py](a2a_tool.py) reads the Agent Card and calls the remote service with the channel key. Both endpoints share one client.

| External request | How the service handles it |
| --- | --- |
| `POST /HiAgent_a2a_http` | Converts `prompt` to an A2A message and returns the remote `Task` or `Message`. |
| `POST /HiAgent_a2a_client` | Accepts standard A2A JSON-RPC and returns the result under `result`. |

## 1. Get the card and key from Hi Agent

1. Choose the target Hi Agent assistant and note its introduction for later verification.
2. Publish it to an **A2A service** channel. Export the complete **Agent Card** and copy the **API key** from that same channel.
3. Save the card as `remote_agentcard.json` in this directory. Check the service address in the card. Both your computer and the deployed Runtime must be able to reach it.

## 2. Start the service locally

Run these commands from the repository root. This example uses Python 3.12.

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/a2a_client
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set the Hi Agent channel key in `.env`.

| Variable | Value |
| --- | --- |
| `HI_AGENT_API_KEY` | Hi Agent A2A channel key from step 1. The service sends it to Hi Agent in the `Apikey` header. |
| `HOST`, `PORT` | Local defaults are `127.0.0.1` and `8000`. Change them if needed. |

Run `python a2a_server.py`. The default address is `http://127.0.0.1:8000`. Run the following requests from another terminal. They call the live Hi Agent assistant.

## 3. Check HTTP and JSON-RPC replies

Set the caller variables first. The local service does not authenticate inbound requests, so leave `APIKEY` empty.

```bash
export BASE_URL='http://127.0.0.1:8000'
export APIKEY=''
```

**HTTP.** Ask the assistant to introduce itself.

```bash
curl -sS --fail-with-body --max-time 65 "$BASE_URL/HiAgent_a2a_http" \
  -H "Authorization: Bearer $APIKEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"请介绍一下你自己。"}'
```

A successful call returns the remote `Task` or `Message`. For a task, inspect `status.state` and `artifacts[].parts`: `completed` means the task has finished, and the text should match the introduction from step 1. For a direct message, read `parts`.

**Standard A2A JSON-RPC.** Send the same question with `message/send`.

```bash
curl -sS --fail-with-body --max-time 65 "$BASE_URL/HiAgent_a2a_client" \
  -H "Authorization: Bearer $APIKEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":"request-1",
    "method":"message/send",
    "params":{
      "message":{
        "role":"user",
        "messageId":"message-1",
        "parts":[{"kind":"text","text":"请介绍一下你自己。"}]
      },
      "configuration":{"blocking":true}
    }
  }'
```

The response `id` should be `request-1`. Read the task state and reply from `result.status.state` and `result.artifacts[].parts`, or `result.parts` for a direct message. The remote assistant determines the wording. Check for a JSON-RPC `error` even when the HTTP status is 200.

Use a new `messageId` for each new message. To test a follow-up, change the question to “What did I just ask you to do?” and pass the previous reply's `contextId`: use HTTP `context_id` or JSON-RPC `message.contextId`. The target assistant must retain the conversation.

## 4. Deploy the service and call it externally

1. With the AgentKit CLI configured, run `ak config -i` in this directory. You can name the application `hiagent_a2a_server`. Choose Python, set the entry point to `a2a_server.py` and the dependencies file to `requirements.txt`. Select `cloud` deployment and `key_auth` for Runtime authentication.
2. Set the application type to `WebServer App`. If the CLI does not offer this option, set `agent_type` under `common` to `WebServer App` in the generated `agentkit.yaml`.
3. Configure the Hi Agent channel key in the Runtime environment using the variable from step 2. Use `HOST` and `PORT` to listen on `0.0.0.0:8000`. Check that `remote_agentcard.json` is in this directory, then run `ak launch`. The Dockerfile copies the two Python files and the card, and excludes the local `.env`.
4. Copy the full Endpoint and API Key from **Quick Invocation** for the new **caller Runtime**. Replace the endpoint below and fill the empty quotes with the Runtime key, then run both curl commands from step 3. Check the task state and Hi Agent reply.

```bash
export BASE_URL='https://<gateway>/runtime/<runtime-id>'
export APIKEY=''
```

Keep the Endpoint's `/runtime/<id>` prefix and omit a trailing `/`. `APIKEY` authenticates access to the AgentKit gateway; the server's `HI_AGENT_API_KEY` authenticates access to Hi Agent.

**Optional: standard A2A client discovery.** Set the Runtime's `PUBLIC_BASE_URL` environment variable to the full Endpoint and apply the configuration. Clients read `/HiAgent_a2a_client/.well-known/agent-card.json`. Use the same `Authorization` header as the curl examples for both card discovery and message requests.

## Troubleshooting

For failed HTTP requests, read the status code and JSON `detail` field. For JSON-RPC failures, read `error`. A remote `input-required` state means more information is needed; continue that conversation.

| Symptom | What to check |
| --- | --- |
| Service fails to start | Check that `remote_agentcard.json` is complete and `HI_AGENT_API_KEY` is set. |
| Cloud request returns 401 or 403 | Check that `BASE_URL` and `APIKEY` belong to the same caller Runtime. |
| HTTP 422 | Supply a nonblank `prompt` string. |
| HTTP 502 or JSON-RPC `error` | Check that the Hi Agent card and channel key match, and that the remote service is available. |
| HTTP 504 | The remote call exceeded 60 seconds. Check access to the Hi Agent address from the service's network. |
| Agent Card still advertises a local address | Check the Runtime's `PUBLIC_BASE_URL`, including the full gateway path. |

## License

[Apache 2.0](../../../../../LICENSE)
