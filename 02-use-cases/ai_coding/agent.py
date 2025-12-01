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
import os
import sys

from agentkit.apps import AgentkitAgentServerApp, AgentkitSimpleApp
from google.adk.planners import BuiltInPlanner
from google.genai import types
from veadk import Agent, Runner
from veadk.memory import ShortTermMemory
from veadk.tools.builtin_tools.run_code import run_code
from veadk.tracing.telemetry.exporters.apmplus_exporter import APMPlusExporter
from veadk.tracing.telemetry.opentelemetry_tracer import OpentelemetryTracer

current_script_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_script_path)
sys.path.append(current_dir)
print(sys.path)

from tools import get_url_of_frontend_code_in_tos, upload_frontend_code_to_tos

logger = logging.getLogger(__name__)
logging.basicConfig(level="INFO")

app = AgentkitSimpleApp()
short_term_memory = ShortTermMemory(backend="local")

tracer = OpentelemetryTracer(exporters=[APMPlusExporter()])

with open('%s/prompt.zh.md'%current_dir, 'r', encoding='utf-8') as f:
    instruction = f.read()
root_agent = Agent(
    description="An AI coding agent that helps users solve programming problems",
    instruction=instruction,
    tools=[run_code, upload_frontend_code_to_tos, get_url_of_frontend_code_in_tos],
    tracers=[tracer],
    short_term_memory=short_term_memory,
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024,
        )
    ),
    model_name='deepseek-v3-1-terminus'

)

app_name = "ai_coding_agent"
runner = Runner(app_name=app_name, agent=root_agent, short_term_memory=short_term_memory)

agent_server_app = AgentkitAgentServerApp(agent=root_agent, short_term_memory=short_term_memory)




if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
