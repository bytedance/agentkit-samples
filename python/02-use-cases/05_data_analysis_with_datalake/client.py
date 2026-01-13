import requests
import httpx
import random

from google.adk.cli.adk_web_server import CreateSessionRequest, RunAgentRequest
from google.genai.types import Content, Part
import asyncio


if __name__ == "__main__":
    # Step 0: setup running configs
    app_name = "data_analysis_with_code"
    user_id = "agentkit_user"
    session_id = "agentkit_sample_session"
    base_url = ""
    api_key = ""

    task_num = 1

    # Step 1: create a session
    def create_session():
        create_session_request = CreateSessionRequest(
            session_id=session_id + f"_{random.randint(1, 9999)}",
        )

        response = requests.post(
            url=f"{base_url}/apps/{app_name}/users/{user_id}/sessions/{create_session_request.session_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )

        print(f"[create session] Response from server: {response.json()}")

        return create_session_request.session_id

    # Step 2: run agent with SSE
    run_agent_request = RunAgentRequest(
        app_name=app_name,
        user_id=user_id,
        session_id=create_session(),
        new_message=Content(
            parts=[Part(text="Ang Lee的电影评分超过7分，有哪些电影海报包含动物")],
            role="user",
        ),
        stream=True,
    )

    print("[run agent] Event from server:")

    # 3. Handle streaming events
    async def send_request(message: str):
        run_agent_request = RunAgentRequest(
            app_name=app_name,
            user_id=user_id,
            session_id=create_session(),
            new_message=Content(parts=[Part(text=message)], role="user"),
            stream=True,
        )

        with httpx.stream(
            "POST",
            f"{base_url}/run_sse",
            json=run_agent_request.model_dump(exclude_none=True),
            timeout=120,
            headers={"Authorization": f"Bearer {api_key}"},
        ) as r:
            for line in r.iter_lines():
                print(line)

    async def send_request_parallel():
        tasks = [
            send_request("Ang Lee的电影评分超过7分，有哪些电影海报包含动物")
            for _ in range(task_num)
        ]
        await asyncio.gather(*tasks)

    asyncio.run(send_request_parallel())
