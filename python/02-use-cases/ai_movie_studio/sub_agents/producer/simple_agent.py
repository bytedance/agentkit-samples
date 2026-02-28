import logging
import os

from agent import (
    agent as producer_agent,
    app_name as APP_NAME,
)

from veadk import Runner
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.models.lite_llm import LiteLlm
from agentkit.apps import AgentkitA2aApp
from a2a.types import AgentCard, AgentProvider, AgentSkill, AgentCapabilities

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

a2a_app = AgentkitA2aApp()

# Use the imported agent
agent_instance = producer_agent

session_service = (
    agent_instance.short_term_memory.session_service
    if agent_instance.short_term_memory
    else None
)
runner = Runner(agent=agent_instance, session_service=session_service)

# Configure App with Events Compaction
runner.app = App(
    name=APP_NAME,
    root_agent=agent_instance,
    events_compaction_config=EventsCompactionConfig(
        summarizer=LlmEventSummarizer(
            llm=LiteLlm(
                model=os.getenv(
                    "EVENTS_COMPACTION_MODEL",
                    "openai/doubao-seed-1-6-lite-251015",
                ),
                api_base=os.getenv(
                    "EVENTS_COMPACTION_API_BASE",
                    "https://ark.cn-beijing.volces.com/api/v3/",
                ),
                api_key=os.getenv(
                    "EVENTS_COMPACTION_API_KEY", os.getenv("MODEL_AGENT_API_KEY", "")
                ),
            ),
            prompt_template=None,
        ),
        compaction_interval=int(os.getenv("EVENTS_COMPACTION_INTERVAL", "3")),
        overlap_size=int(os.getenv("EVENTS_COMPACTION_OVERLAP_SIZE", "1")),
    ),
)

@a2a_app.agent_executor(runner=runner)
class ProducerAgentExecutor(A2aAgentExecutor):
    async def run(self, *args, **kwargs):
        try:
            return await super().run(*args, **kwargs)
        except Exception as e:
            logger.exception("Error executing agent request")
            raise e


@a2a_app.ping
def ping() -> str:
    return "pong!"


if __name__ == "__main__":
    agent_card = AgentCard(
        capabilities=AgentCapabilities(streaming=True),
        description=agent_instance.description,
        name=APP_NAME,
        default_input_modes=["text"],
        default_output_modes=["text"],
        provider=AgentProvider(organization="volcengine", url=""),
        skills=[
            AgentSkill(
                id="producer_chat",
                name="producer_chat",
                description="统筹创意、制作与评审",
                tags=["chat", "producer", "movie"],
            )
        ],
        url="http://0.0.0.0:8000",
        version="1.0.0",
    )

    port = int(os.getenv("PORT", "8000"))
    a2a_app.run(
        agent_card=agent_card,
        host="0.0.0.0",
        port=port,
    )
