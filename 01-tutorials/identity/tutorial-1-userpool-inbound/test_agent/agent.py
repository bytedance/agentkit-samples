
from veadk import Runner, Agent
from agentkit.apps import AgentkitSimpleApp
from veadk.tools.demo_tools import get_city_weather
app = AgentkitSimpleApp()
agent = Agent(model_name="doubao-seed-1-6-251015", tools=[get_city_weather])
runner = Runner(agent=agent)

@app.entrypoint
async def run(payload: dict, headers: dict) -> str:
    prompt = payload["prompt"]
    if prompt is None:
        return "prompt is None"

    user_id = headers.get("user_id", "testuser")
    session_id = headers.get("session_id", "testsession")

    response = await runner.run(
        messages=prompt,
        user_id=user_id,
        session_id=session_id
    )
    return response

@app.ping
def ping() -> str:
    return "pong!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
