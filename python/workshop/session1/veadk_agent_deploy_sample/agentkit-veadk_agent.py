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

"""
**AgentKit Wrapper for User-Defined Agent**

This file wraps your Agent definition (veadk_agent.py) to make it deployable with AgentKit.

Your Agent is imported from: veadk_agent
Agent variable: agent
"""

import logging

# Import user's Agent definition
from veadk_agent import agent

from veadk import Runner
from agentkit.apps import AgentkitSimpleApp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


app = AgentkitSimpleApp()

# Use user's Agent
runner = Runner(agent=agent)


@app.entrypoint
async def run(payload: dict, headers: dict) -> str:
    """
    Main entrypoint for the Agent.

    This wrapper handles the standard AgentKit request/response protocol
    and delegates to your Agent for processing.
    """
    prompt = payload["prompt"]
    user_id = headers["user_id"]
    session_id = headers["session_id"]

    logger.info(
        f"Running agent with prompt: {prompt}, user_id: {user_id}, session_id: {session_id}"
    )

    response = await runner.run(messages=prompt, user_id=user_id, session_id=session_id)

    logger.info(f"Run response: {response}")
    return response


@app.ping
def ping() -> str:
    """Health check endpoint."""
    return "pong!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
