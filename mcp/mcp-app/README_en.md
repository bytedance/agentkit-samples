# MCP App · Flight Assistant (locally testable)

A **locally testable MCP App** sample: MCP tools return structured data only, and a
same-origin frontend renders each tool's output as an interactive App UI.

> Reference: https://modelcontextprotocol.io/extensions/apps/build

## What is an MCP App

An MCP App is a way to build interactive frontends on top of MCP:

- The server exposes **tools** that return structured data (the data contract);
- A client / embedded webview renders the data as a matching **App UI** per tool type;
- One MCP server can host the MCP endpoint, the App frontend, and the App manifest.

This sample demonstrates the pattern with FastMCP + FastAPI, fully local, no external services.

## Layout

| File | Description |
| - | - |
| `server.py` | FastMCP server + FastAPI hosting `/` (frontend), `/app.json` (manifest), `/mcp` (MCP endpoint) |
| `index.html` | App frontend: search flights → click for detail → live tracking |
| `app.json` | App manifest: id, entry, MCP endpoint, and the tool contract |
| `test_mcp_app.py` | Offline smoke test (in-process HTTP, no browser/port needed) |
| `requirements.txt` | Python dependencies |

## Data contract (tool → App UI)

| Tool | Input | Output | UI |
| - | - | - | - |
| `search_flights` | `from_city, to_city, date` | flight list | clickable flight cards |
| `get_flight` | `flight_id` | flight detail | detail card (model/gate/price/status) |
| `track_flight` | `flight_id` | flight timeline | timeline view |

Every UI call is a standalone `tools/call` request (stateless + JSON), no initialize handshake needed.

## Run locally

Requires Python 3.10+.

```bash
cd mcp/mcp-app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --port 8000
```

Open http://127.0.0.1:8000 to use the App UI:

- Enter departure/arrival cities → **Search flights**
- Click a flight card to fill the flight number → **View detail** / **Live tracking**

Other endpoints:

- MCP endpoint: `POST http://127.0.0.1:8000/mcp`
- App manifest: `GET http://127.0.0.1:8000/app.json`

## Test locally (no server needed)

```bash
cd mcp/mcp-app
python test_mcp_app.py
```

The test drives the real app in-process via FastAPI `TestClient`, covering the frontend page,
App manifest, `tools/list`, the `tools/call` data contract for all three tools, the error path,
and `/docs`.

## Connect an MCP Apps client

1. Add the service to your client's MCP config (Streamable HTTP): `http://127.0.0.1:8000/mcp`
2. Call `tools/list` to discover the tools;
3. Call `search_flights` / `get_flight` / `track_flight` to get structured data;
4. Render each result as its App UI according to the contract declared in `app.json`.
