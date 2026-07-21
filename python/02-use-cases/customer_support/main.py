"""customer_support — a VeADK agent served as an AgentKit runtime.

Served as the standard **ADK API server** via `AgentkitAgentServerApp`: it
exposes `/list-apps`, `/run_sse` (streaming), `/run`, session and artifact
management — the same API the AgentKit console and the Feishu proxy talk to.
The process must listen on `0.0.0.0:8000` (the runtime probes that port).

The agent itself lives in the `assistant` package (`assistant/agent.py`) so it
can be reused: this module wires it into the API server, while the veADK
Frontend (`veadk frontend`) discovers the same package directly.
"""

from veadk.memory.short_term_memory import ShortTermMemory
from agentkit.apps import AgentkitAgentServerApp

from assistant import root_agent

# In-memory sessions. Swap the backend (sqlite / mysql / postgresql) for a
# persistent store — see veadk.memory.short_term_memory.ShortTermMemory.
short_term_memory = ShortTermMemory(backend="local")

# The ADK API server. `app` is the ASGI app, so `uvicorn main:app` also works.
server = AgentkitAgentServerApp(agent=root_agent, short_term_memory=short_term_memory)
app = server.app


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8000)
