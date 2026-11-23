# Call Hi Agent from AgentKit

[Bidirectional sample](../README_en.md) · [中文](README.md)

## Call flow

**Caller on AgentKit Runtime (this directory) → `remote_agent` tool → Hi Agent A2A service → target assistant in Hi Agent**

This directory implements the caller for POC 1. AgentKit Runtime provides the execution environment outside Hi Agent. The caller model uses the `remote_agent` tool to send a task to Hi Agent. The target assistant handles the request, and the tool returns its reply to the caller.

You need a model that supports tool calls. In Hi Agent, choose or create a test agent and publish it as an A2A service in the next step.

## 1. Get the card and key from Hi Agent

1. Open the target agent in Hi Agent. Choose a distinctive phrase from its introduction, or give it one to use during testing.
2. Publish the agent to the **A2A service** channel. Export the complete **Agent Card** and copy the **API key** from that same channel.
3. Save the card as `remote_agentcard.json` in this directory, alongside `veadk_agent.py`. Check the `url` in the card. Your computer must be able to reach it for local testing, and the caller Runtime must be able to reach it after deployment.

## 2. Configure the caller model and channel key

These commands use Python 3.12. Start at the root of the samples repository and stay in `a2a_caller/` for the remaining steps.

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/a2a_caller
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set these four variables in `.env`.

| Variable | Value |
| --- | --- |
| `MODEL_AGENT_NAME` | Caller model name or inference endpoint ID from your model provider’s API example |
| `MODEL_AGENT_API_BASE` | OpenAI-compatible API base for that model. Keep the version path and omit the trailing `/chat/completions` |
| `MODEL_AGENT_API_KEY` | API key authorized to call that model |
| `HI_AGENT_API_KEY` | Hi Agent A2A channel key from step 1. The tool sends it in the `Apikey` header |

## 3. Call Hi Agent locally

```bash
python veadk_agent.py
```

The script asks the remote agent to introduce itself and asks the caller to repeat the reply verbatim. Look for the phrase you chose in step 1 in the terminal output.

To check the HTTP service entry point used for deployment, start the server.

```bash
python agent_server.py
```

In another terminal, run this command.

```bash
curl -fsS http://127.0.0.1:8000/list-apps
```

Both this caller and the target in the reverse example use the application name `simple_agent`. Seeing that name confirms that a local HTTP service is running. Check that you started it in `a2a_caller/` and use the self-introduction above to verify the remote call. Press Ctrl+C in the server terminal when finished.

## 4. Deploy the caller and verify the tool call

Sign in to the AgentKit CLI (`ak`) with access to a project where you can deploy a Runtime. Run `ak config -i` in `a2a_caller/`.

| Setting | Value |
| --- | --- |
| Application name | Give the caller a distinct name, such as `hiagent-a2a-caller` |
| Language, entry point, dependencies | `Python`, `agent_server.py`, `requirements.txt` |
| Deployment and authentication | `cloud`, your project and region, `key_auth` |
| Runtime environment variables | The four variables from step 2. The image build excludes your local `.env` |

Check that `remote_agentcard.json` is in the current directory, then deploy.

```bash
ak launch
```

Open the new **caller Runtime** and send “Call the remote agent and repeat its self-introduction verbatim” in its online test. Look for `remote_agent` in the tool trace and check the introduction in the tool result. To give another client access to this caller, copy its endpoint and API key from the caller Runtime’s **Quick Invocation** (快速调用) page.

If the remote request returns 401, check that the card and `HI_AGENT_API_KEY` came from the same agent’s A2A channel in Hi Agent. If the local call succeeds but the cloud call times out, check whether the caller Runtime can reach the address in the card.
