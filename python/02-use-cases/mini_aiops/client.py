import asyncio
import httpx
import requests
import random
from google.adk.cli.adk_web_server import CreateSessionRequest, RunAgentRequest
from google.genai.types import Content, Part

if __name__ == "__main__":
    # Step 0: setup running configs
    app_name = "root_agent"
    user_id = "agentkit_user"
    session_id = "agentkit_session"
    base_url = "http://127.0.0.1:8000"
    api_key = "test key"

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

        try:
            with httpx.stream(
                "POST",
                f"{base_url}/run_sse",
                json=run_agent_request.model_dump(exclude_none=True),
                timeout=120,
                headers={"Authorization": f"Bearer {api_key}"},
            ) as r:
                for line in r.iter_lines():
                    print(line)
        except Exception as e:
            print(f"Error: {e}")

    async def send_request_parallel():
        await send_request("查看现有的 TLS 实例")

    asyncio.run(send_request_parallel())
