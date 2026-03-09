# MCP Simple

This case demonstrates how to use the MCP protocol to allow an Agent to use external tools.

## What is MCP

MCP (Model Context Protocol) is a set of protocols for models to interact with external services. In the Agent-SDK, we provide an implementation of MCP based on HTTP.

In this case, we will demonstrate how to use the MCP protocol to allow an Agent to use external tools.

## How to Run

### 1. Start the MCP Server

First, we need to start an MCP Server, which will provide external tools for the Agent.

In this case, we have already prepared a `tos_mcp_server.py` for you. You just need to run the following command in the terminal:

```bash
python tos_mcp_server.py
```

> **Note**
>
> Before starting, please fill in your TOS AK, SK, Endpoint, Region, and Bucket in `config.json`, otherwise `tos_mcp_server` will not work properly.

### 2. Run main.py

After the MCP Server starts, we can run `main.py`.

In `main.py`, we first create an `MCPToolset`, which is a Toolset that can connect to the MCP Server and expose its tools to the Agent.

```python
# ...
tos_mcp_runner = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=url,
        timeout=120
    ),
)
# ...
```

Then, we create an Agent and pass `tos_mcp_runner` as a tool.

```python
# ...
root_agent = Agent(
    name="tos_mcp_agent",
    instruction="You are an object storage management expert, proficient in various object storage operations using the MCP protocol.",
    tools=[tos_mcp_runner],
)
# ...
```

Finally, we start the Agent and interact with it.

```bash
python main.py
```

## Expected Results

After running `main.py`, you will see an interactive command-line interface where you can converse with the Agent.

You can try giving instructions to the Agent, such as: "List all files in the current bucket", and the Agent will call the tools in `tos_mcp_server` and return the results.
