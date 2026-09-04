import logging
import os

from agent import car_unified_agent, APP_NAME, DESCRIPTION

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

session_service = (
    car_unified_agent.short_term_memory.session_service if car_unified_agent.short_term_memory else None
)
runner = Runner(agent=car_unified_agent, session_service=session_service)
runner.app = App(
    name=APP_NAME,
    root_agent=car_unified_agent,
    events_compaction_config=EventsCompactionConfig(
        summarizer=LlmEventSummarizer(
            llm=LiteLlm(
                model=os.getenv("EVENTS_COMPACTION_MODEL", "openai/doubao-seed-1-6-lite-251015"),
                api_base=os.getenv("EVENTS_COMPACTION_API_BASE", "https://ark.cn-beijing.volces.com/api/v3/"),
                api_key=os.getenv("EVENTS_COMPACTION_API_KEY", os.getenv("MODEL_AGENT_API_KEY", "")),
            ),
            prompt_template=None,
        ),
        compaction_interval=int(os.getenv("EVENTS_COMPACTION_INTERVAL", "3")),
        overlap_size=int(os.getenv("EVENTS_COMPACTION_OVERLAP_SIZE", "1")),
    ),
)


@a2a_app.agent_executor(runner=runner)
class CarUnifiedAgentExecutor(A2aAgentExecutor):
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
        description=DESCRIPTION,
        name=APP_NAME,
        default_input_modes=["text"],
        default_output_modes=["text"],
        provider=AgentProvider(organization="volcengine", url=""),
        skills=[
            AgentSkill(
                id="car_unified",
                name="car_unified",
                description="一体化选车+算账+交付",
                tags=["chat", "car", "unified"],
            )
        ],
        url="http://0.0.0.0:8000",
        version="1.0.0",
    )

    a2a_app.run(
        agent_card=agent_card,
        host="0.0.0.0",
        port=8000,
    )
