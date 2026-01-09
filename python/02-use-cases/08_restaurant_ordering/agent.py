# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

# Deploy the agent as AgentkitAgentServerApp into the agentkit platform
from agentkit.apps import AgentkitAgentServerApp
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.apps.app import EventsCompactionConfig
from google.adk.models.llm_request import LlmRequest
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.plugins.context_filter_plugin import ContextFilterPlugin
from google.adk.plugins.save_files_as_artifacts_plugin import (
    SaveFilesAsArtifactsPlugin,
)
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from veadk.agent import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.web_search import web_search

logger = logging.getLogger(__name__)
short_term_memory = ShortTermMemory(backend="local")


RECIPES = (
    "Kung Pao Chicken",
    "Mapo Tofu",
    "Sweet and Sour Pork",
    "Peking Duck",
    "Wonton Soup",
    "Dumplings",
    "Chow Mein",
    "Spring Rolls",
    "Fried Rice",
    "Hot and Sour Soup",
)


async def add_to_order(dish_name: str, tool_context: ToolContext = None) -> str:
    """Adds a dish to the user's order.

    Args:
      dish_name: The exact name of the dish from the menu to add to the order.

    Returns:
      A confirmation message that the dish has been added.
    """
    if "order" not in tool_context.state:
        tool_context.state["order"] = []

    tool_context.state["order"] = tool_context.state["order"] + [dish_name]
    return f"I've added {dish_name} to your order."


async def summarize_order(tool_context: ToolContext = None) -> str:
    """Summarizes the user's current order.

    Returns:
    A string containing the list of ordered dishes.
    """
    order = tool_context.state.get("order", [])
    if not order:
        return "You haven't ordered anything yet."

    summary = "Here is your order so far:\n" + "\n".join(f"- {dish}" for dish in order)
    return summary


order_agent = Agent(
    name="restaurant_ordering_agent",
    description=("An agent that takes customer orders at a restaurant."),
    instruction=f"""
        You are a friendly and efficient order-taking assistant for a restaurant.
        Your goal is to help the user choose items from the menu and add them to their order.
        
        The menu contains the following dishes: {", ".join(RECIPES)}.
        
        **Workflow:**
        1.  **Understand the user's request.** Use your semantic understanding to match their request (e.g., 'something spicy', 'a chicken dish') to a specific item on the menu.
        2.  **Confirm and Add to Order.** Once you have identified a dish the user wants, you MUST call the `add_to_order` tool with the *exact* dish name from the menu. You can using parallel invocations to add multiple dishes to the order.
        3.  **Handle Off-Menu Requests.** If a user asks for a dish that is not on the menu, you MUST use the `web_search` tool to find information about that dish. Then, ask the user if they would like the kitchen to prepare it as a special item. If they agree, you MUST call the `add_to_order` tool to add the special dish to their order.
        4.  **Summarize.** When the user indicates they are finished (e.g., 'that's all', 'check please'), you MUST call the `summarize_order` tool and present the final order to the user.
        
        **Rules:**
        - Do NOT provide recipes or cooking instructions.
    """,
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
        ),
    ),
    generate_content_config=types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            ),
        ]
    ),
    tools=[
        add_to_order,
        summarize_order,
        web_search,
    ],
)


class CountInvocationPlugin(BasePlugin):
    """A custom plugin that counts agent and tool invocations."""

    def __init__(self) -> None:
        """Initialize the plugin with counters."""
        super().__init__(name="count_invocation")
        self.agent_count: int = 0
        self.tool_count: int = 0
        self.llm_request_count: int = 0

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        """Count agent runs."""
        self.agent_count += 1
        print(f"[Plugin] Agent run count before_agent_callback: {self.agent_count}")

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> None:
        """Count LLM requests."""
        self.llm_request_count += 1
        print(
            f"[Plugin] LLM request count before_model_callback: {self.llm_request_count}"
        )


root_agent = order_agent

app = App(
    name="restaurant_ordering",
    root_agent=root_agent,
    plugins=[
        CountInvocationPlugin(),
        ContextFilterPlugin(
            num_invocations_to_keep=8
        ),  # 如果需要精确控制保留轮数,使用 ContextFilterPlugin
        SaveFilesAsArtifactsPlugin(),
    ],
    # events_compaction_config 用于配置事件压缩，以在长对话中节省上下文。
    # compaction_interval=3: 每3次调用触发一次压缩。
    # overlap_size=1: 压缩时保留前一个窗口的最后一次调用。
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,  # Trigger compaction every 3 new invocations.
        overlap_size=1,  # Include last invocation from the previous window.
    ),
)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
