# Call an AgentKit Runtime from a Hi Agent HTTP plugin

[中文](README.md) · [Back to the integration sample](../README_en.md)

## Call flow

**Hi Agent assistant → Hi Agent HTTP plugin → HTTP adapter (this directory) → target agent on AgentKit**

This directory implements the adapter for the supplementary HTTP example. The adapter and the target agent run on separate AgentKit Runtimes when deployed. The Hi Agent plugin sends a `POST /` request to the adapter. The adapter converts the request and calls the target at `UPSTREAM_BASE_URL` (`simple_agent` in this sample).

The target agent generates the reply. The adapter sends it back to the Hi Agent plugin as a single JSON response or as text streamed over SSE.

The adapter handles two issues observed during integration. The plugin sometimes encoded a JSON object a second time and sent it as a string. Sending that body directly to the target Runtime produced HTTP 422. The plugin's streaming reader also required the exact response type `text/event-stream`. It could not read a response with an added `charset` parameter.

## 1. Choose a target agent

For a first run, deploy the sample `simple_agent`. Copy the full Endpoint and API Key from **Quick Invocation (快速调用)** on the target Runtime page. [Target agent deployment guide](../simple_agent/README_en.md)

You can also use an existing deployment. Its Runtime must support the routes for your chosen mode. It can return an array of ADK events or an SSE stream with a JSON event in each data frame. The adapter extracts model text and skips user messages and reasoning parts. All target paths below are relative to its Endpoint.

| Plugin request | Requests the adapter sends to the target Runtime |
| --- | --- |
| Regular `POST /` | Calls `POST /invoke` with the body `{"prompt":"…"}` and the headers `user_id` and `session_id`. |
| Streaming `POST /` with `streaming=true` | Creates a session with `POST /apps/{app}/users/{user}/sessions/{session}`, then calls `POST /run_sse`. A 409 on session creation means the session already exists and the call can proceed. |
| Explicit `POST /run` on the adapter | Uses the same session route, then calls the target's `POST /run` and reads an array of ADK events. This route serves regular replies only. |

## 2. Start the adapter locally

Run these commands from the repository root. This example uses Python 3.12.

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/http_plugin
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set the target values in `.env`.

| Variable | Value |
| --- | --- |
| `UPSTREAM_BASE_URL` | Full target Runtime Endpoint, including its `/runtime/<id>` prefix if present. The adapter appends the operation paths. |
| `UPSTREAM_API_KEY` | Raw API Key for the target Runtime. The adapter adds the `Bearer` prefix. |
| `UPSTREAM_APP_NAME` | Target ADK application name. Defaults to `simple_agent`. The adapter uses it in the session URL and the `app_name` field sent to `/run_sse` and `/run`. The regular `/invoke` call does not require it. |

Run `python plugin_server.py`. The default address is `http://127.0.0.1:8000`. Run the following requests from another terminal. They call the live target agent.

## 3. Check the JSON reply and streaming events

First reproduce the plugin's double encoding. Keep the outer double quotes and the backslashes in the request body. The adapter also accepts a regular JSON object.

```bash
curl -sS -i http://127.0.0.1:8000/ \
  -H 'Content-Type: application/json' \
  --data-binary '"{\"message\":\"Please introduce yourself.\",\"user_id\":\"user1\",\"session_id\":\"chat1\"}"'
```

Expect HTTP 200 and a body with a single string field, `output`. For example, `{"output":"I am Agentkit-01."}`. The target agent determines the wording.

If your target only provides `/invoke`, this completes the check for regular replies. To test a follow-up, change the message in the first command to “What did I just ask you to do?” Keep the same `user_id` and `session_id`. The target must retain that session.

**Optional streaming check.** Run the next command if your target supports ADK session creation and `/run_sse`. It reuses the two IDs from the first request. The adapter uses `plugin_user` if you omit `user_id` and generates a fresh ID for each request if you omit `session_id`.

```bash
curl -sS -i -N http://127.0.0.1:8000/ \
  -H 'Content-Type: application/json' \
  --data-binary '{"message":"What did I just ask you to do?","user_id":"user1","session_id":"chat1","streaming":true}'
```

`-i` shows the response headers. `-N` displays events as they arrive. Check that the `Content-Type` value is exactly `text/event-stream`, with no `charset`. Each `message` carries a chunk of visible text in `content`. A successful stream ends with `close`.

```text
event: message
data: {"content":"You asked me to introduce myself."}

event: close
data: closed
```

If the upstream fails after streaming starts, the last event is `error`. Read `error_msg` and mark the reply as failed. Check the terminal event even if the status is HTTP 200 or some text has arrived. If the upstream's final text revises content already sent, the stream ends with `error`. You can send a regular request to get the complete text for that new call.

```text
event: error
data: {"error_msg":"上游 Agent 执行失败"}
```

To check local behavior with a simulated upstream, run `python -m unittest discover -s tests -v` in this directory.

## 4. Deploy the adapter and connect Hi Agent

1. With the AgentKit CLI configured, run `ak config -i` in this directory. Give the adapter its own deployment name. Choose Python, set the entry point to `plugin_server.py` and the dependencies file to `requirements.txt`. Select `cloud` deployment and `key_auth` for Runtime authentication.
2. In the adapter's cloud environment, set `UPSTREAM_BASE_URL` and `UPSTREAM_API_KEY` for the **target** Runtime. Set `UPSTREAM_APP_NAME` if the target has a different ADK application name. The image excludes the local `.env` file. Run `ak launch`.
3. Copy the Endpoint and API Key from **Quick Invocation** for the **adapter Runtime**. Create an HTTP plugin in Hi Agent. Choose `POST` and enter the full adapter Endpoint followed by `/`. Set the headers to `Content-Type: application/json` and `Authorization: Bearer <adapter Runtime API Key>`. Hi Agent uses the adapter credentials. The adapter uses the target credentials from step 2.
4. Add the required string field `message`. For regular replies, set the response field `output` to string. For multi-turn calls, add the string fields `user_id` and `session_id`. If you also need streaming, add the optional boolean `streaming`. Test with `streaming=true` and check for `message` and `close` events.
5. Publish the plugin and add its tool to your Hi Agent agent. In the conversation, ask “Use this tool to ask the remote agent to introduce itself, then repeat its reply.” Inspect the result in the tool call record. The sample target mentions `Agentkit-01`. For your own target, check its answer.

## Troubleshooting

For a failed regular request or a failure before streaming starts, read the HTTP status and the JSON `detail` field. Once streaming starts, inspect the last event.

| Symptom | What to check |
| --- | --- |
| 401 or 403 | Check the adapter Key in the plugin header. If `detail` reports an upstream HTTP error, check that the target Key and Endpoint in the adapter environment belong to the same Runtime. |
| Regular calls work but streaming returns 404 | Check the target's ADK application name, session creation route, and `/run_sse`. A regular call to the root route uses only `/invoke`. |
| 422 | Supply a nonblank `message` string. Both IDs must be safe for HTTP headers and URL path segments. For streaming, use the root route with `streaming=true`. |
| 503, 502, or 504 | For a missing Key, set the adapter's `UPSTREAM_API_KEY`. For connection failures or timeouts, check that the adapter's network can reach the target Endpoint. For invalid or missing text, inspect the target's ADK events. |
| The plugin shows no text or stops mid-reply | Use the `curl -i -N` example to check the response headers, `message.content`, and the last event. Read `error_msg` for an `error` event. If partial text arrives and the terminal event is missing, check for a dropped connection. |

## License

[Apache 2.0](../../../../../LICENSE)
