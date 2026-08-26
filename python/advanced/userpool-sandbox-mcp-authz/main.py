"""Optional AgentKit Agent Server entrypoint for the experiment agent."""

from assistant import root_agent
from agentkit.apps import AgentkitAgentServerApp


server = AgentkitAgentServerApp(
    agent=root_agent,
    enable_auth=True,
)
app = server.app


__all__ = ["app", "root_agent", "server"]


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8000)
