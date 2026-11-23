# Calls between Hi Agent and AgentKit Runtime

[中文](README.md)

## Scenario

This sample uses Hi Agent to show how AgentKit and external agents can call each other. It includes the code for both directions.

Hi Agent is an external platform running in a private cloud. You can follow the same approach to connect agents on other hybrid-cloud platforms.

- **AgentKit → Hi Agent (POC 1).** AgentKit Runtime stands in for a sandbox outside Hi Agent. The caller reads the service address from the Agent Card, sends an A2A request with the Hi Agent channel key, and receives the remote agent’s reply.
- **AgentKit → Hi Agent (POC 1.1).** An external caller sends HTTP or JSON-RPC requests to the Runtime. Its A2A Client calls Hi Agent directly through `/HiAgent_a2a_http` or `/HiAgent_a2a_client`.
- **Hi Agent → AgentKit (POC 2).** The Hi Agent MCP plugin connects to the MCP server deployed on AgentKit. A tool on the server calls the target agent over A2A and returns the result to Hi Agent.
- **HTTP plugin alternative.** A Hi Agent HTTP plugin can call the same target through an HTTP adapter. The adapter forwards the request and returns the reply as JSON or an event stream. You can run the MCP and HTTP examples independently.

For other platforms, the integration depends on the interfaces each side supports. When AgentKit makes the call, it uses the external agent’s protocol and authentication method. In the other direction, AgentKit Runtime already supports A2A and HTTP. A compatible external caller can call the Runtime directly if it can reach the service and authenticate.

## The five sample projects

| Project and run guide | Experiment | What the code does | Source |
| --- | --- | --- | --- |
| [a2a_caller](a2a_caller/README_en.md) | POC 1 | The caller on AgentKit. It reads the service address from the Agent Card exported by Hi Agent and sends the question over A2A. | [Caller](a2a_caller/veadk_agent.py) · [Runtime entry point](a2a_caller/agent_server.py) |
| [a2a_client](a2a_client/README_en.md) | POC 1.1 | Runs an A2A Client in the Runtime, accepts HTTP or JSON-RPC requests, and returns the Hi Agent result. | [Server entry point](a2a_client/a2a_server.py) · [Client implementation](a2a_client/a2a_tool.py) |
| [simple_agent](simple_agent/README_en.md) | POC 2 and the HTTP experiment | The target agent for both experiments. When asked to introduce itself, it replies “我是Agentkit-01” (“I am Agentkit-01”). | [Agent definition](simple_agent/veadk_agent.py) |
| [mcp_server](mcp_server/README_en.md) | POC 2 | The server the Hi Agent MCP plugin connects to. It exposes a tool that calls `simple_agent` over A2A and returns the answer. | [Tool implementation](mcp_server/mcp_tool.py) · [Server entry point](mcp_server/mcp_server.py) |
| [http_plugin](http_plugin/README_en.md) | HTTP experiment | The service called by the Hi Agent HTTP plugin. It forwards the message to `simple_agent` and returns the answer in one response or as a stream. | [Server entry point](http_plugin/plugin_server.py) |

## Run an experiment

- **To reproduce POC 1**, follow the `a2a_caller` guide. Get the Agent Card and channel key from Hi Agent and configure the caller’s model. Run `python veadk_agent.py` in that directory to try the call from your machine. Then deploy the caller with `agent_server.py` as the entry point. In the Runtime’s online test, ask the remote agent to introduce itself and check the answer returned by `remote_agent`.
- **To reproduce POC 1.1**, follow the `a2a_client` guide. Get the Hi Agent card and channel key, then start `python a2a_server.py`. After deployment, set `BASE_URL` and `APIKEY`, run the HTTP and JSON-RPC curl examples, and check the task state and remote reply.
- **To reproduce POC 2**, deploy `simple_agent` or reuse a target Runtime that supports A2A. Then deploy `mcp_server`, sync its tools in Hi Agent, and add the tool to your agent. Call the tool and check the target’s introduction in the result. For the sample target, look for “我是Agentkit-01”.
- **To try the HTTP plugin**, deploy or reuse `simple_agent`, then follow the `http_plugin` guide to deploy the adapter. Set the HTTP plugin URL in Hi Agent to the adapter’s endpoint. Add the plugin to your agent, ask it to call the remote agent in chat, and check the reply in the tool result.

## License

This sample uses the [Apache 2.0 license](../../../../LICENSE).
