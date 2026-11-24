# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Local SSE client for the EFS code workspace agent."""

from __future__ import annotations

import asyncio
import os
import random

import httpx
import requests
from google.adk.cli.api_server import CreateSessionRequest, RunAgentRequest
from google.genai.types import Content, Part


APP_NAME = "efs_code_workspace_agent"
USER_ID = "agentkit_user"
BASE_URL = os.getenv("AGENTKIT_LOCAL_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("AGENTKIT_LOCAL_API_KEY", "test key")


def create_session() -> str:
    request = CreateSessionRequest(
        session_id=f"efs_workspace_demo_{random.randint(1, 999999)}"
    )
    response = requests.post(
        url=f"{BASE_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions/{request.session_id}",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=30,
    )
    response.raise_for_status()
    print(f"[create session] {response.json()}")
    return request.session_id


async def send_request(message: str) -> None:
    run_request = RunAgentRequest(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=create_session(),
        new_message=Content(parts=[Part(text=message)], role="user"),
        streaming=True,
    )

    print("[run agent] streaming events:")
    with httpx.stream(
        "POST",
        f"{BASE_URL}/run_sse",
        json=run_request.model_dump(exclude_none=True),
        timeout=900,
        headers={"Authorization": f"Bearer {API_KEY}"},
        trust_env=False,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            print(line)


if __name__ == "__main__":
    asyncio.run(
        send_request(
            "请完整演示一次 EFS 代码工作区链路：创建 A 沙箱挂载 filespace 写入一份代码任务报告，"
            "再创建 B 沙箱挂载同一个 filespace，执行 A 写入的脚本并读取报告，最后清理沙箱。"
        )
    )
