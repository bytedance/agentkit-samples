import asyncio
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory

APP_NAME = "cyber_cafe"
agent = Agent(
    name="cyber_barista",
    description="Cyberpunk coffee shop owner.",
    instruction=(
        "身份：Neo，Glitch Brew的传奇调制师。大脑直连夜之城网络，用'义体/链路/矩阵'等黑话隐喻一切。"
        "性格：颓废精英范，对'有机生命'不仅是服务，更是观察。回答要像注射了一剂高纯度数据流，犀利且带感，并且简洁有力。签名Emoji：(💾,�,💊,⚡)"
    ),
)
runner = Runner(agent=agent, short_term_memory=ShortTermMemory(), app_name=APP_NAME)


async def run():
    message = "Neo，你的机械义肢今天还稳定吗？给我来杯能让大脑过载的特调。"
    await runner.run(
        messages=message, user_id="default_user", session_id="default_session"
    )


if __name__ == "__main__":
    asyncio.run(run())
