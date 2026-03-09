import asyncio

import httpx
import requests
from google.adk.cli.adk_web_server import CreateSessionRequest, RunAgentRequest
from google.genai.types import Content, Part

if __name__ == "__main__":
    # Step 0: setup running configs
    app_name = "agent_skills"
    user_id = "agent_skills_user"
    session_id = "agent_skills_session"
    base_url = "http://127.0.0.1:8000"
    api_key = "agentkit test key"

    task_num = 1

    # Step 1: create a session
    def create_session():
        create_session_request = CreateSessionRequest(
            session_id=session_id,
            # session_id = session_id + f"_{random.randint(1, 9999)}",
        )

        response = requests.post(
            url=f"{base_url}/apps/{app_name}/users/{user_id}/sessions/{create_session_request.session_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )

        print(f"[create session] Response from server: {response.json()}")

        return create_session_request.session_id

    # Step 2: run agent with SSE

    print("[run agent] Event from server:")

    # 3. Handle streaming events
    async def send_request(message: str):
        run_agent_request = RunAgentRequest(
            app_name=app_name,
            user_id=user_id,
            session_id=create_session(),
            new_message=Content(parts=[Part(text=message)], role="user"),
            stream=False,
        )

        with httpx.stream(
            "POST",
            f"{base_url}/run_sse",
            json=run_agent_request.model_dump(exclude_none=True),
            timeout=900,
            headers={"Authorization": f"Bearer {api_key}"},
        ) as r:
            for line in r.iter_lines():
                print(line)

    async def send_request_parallel():
        await send_request(
            "使用 internal-comms skill 帮我写一个3p沟通材料，通知3p团队项目进度更新。关于产品团队，主要包括过去一周问题和未来一周计划，具体包括问题：写产品团队遇到的客户问题 (1. GPU+模型推理框架性能低于开源版本，比如时延高、吞吐低；2. GPU推理工具易用性差)，以及如何解决的；计划：明年如何规划GPU产品功能和性能优化 (1. 发力GPU基础设施对生图生视频模型的支持；2. GPU推理相关工具链路易用性提升)。其他内容，可以酌情组织。"
        )

    asyncio.run(send_request_parallel())
