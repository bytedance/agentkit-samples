from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
import asyncio
from veadk.tools.builtin_tools.playwright import playwright_tools

app_name = "agent_skills_app"
user_id = "agent_skills_user"
session_id = "agent_skills_skillspaceid_localrun_session"

# 待转换的源文件
file_to_skill_01 = "/Users/bytedance/workspace/github/agentkit-samples/python/01-tutorials/04-agentkit-tools/genius_skills/google_youtube_playback.txt"
file_to_skill_02 = "/Users/bytedance/workspace/github/agentkit-samples/python/01-tutorials/04-agentkit-tools/genius_skills/agentkit_e2e_ops.txt"
# 生成的 skill 存储路径
skills_save_path = "/Users/bytedance/workspace/github/agentkit-samples/python/01-tutorials/04-agentkit-tools/genius_skills/sample-ops-skills"

# skill_space_id = os.getenv("SKILL_SPACE_ID")
skill_space_id = "ss-yefl2g0u0w3fitwlq8ub"  # 替换为实际的 skill space id
agent = Agent(
    name="skill_agent",
    instruction="""
    根据用户的需求，执行 skills，完成任务。
    注意：skills 文件在 AgentKit skill space 中，运行完全在本地。""",
    skills=[skills_save_path],
    skills_mode="local",
    tools=[playwright_tools],
)

short_term_memory = ShortTermMemory(backend="local")

runner = Runner(
    agent=agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id,
)


async def main():
    # messages = """
    # 请运行以下工作流程：
    # 1. 帮我写一个pdf处理的skill，能够支持加载pdf、编辑pdf和从pdf中提取文字信息即可。
    # 2. 输出生成skill所在的文件系统地址。
    # """
    # messages = """
    # 请运行以下工作流程：
    # 1. 将以下两个路径的txt文件分别转换成两个skill：
    #     file_to_skill_01 = "/Users/bytedance/workspace/github/agentkit-samples/python/01-tutorials/04-agentkit-tools/genius_skills/google_youtube_playback.txt"
    #     file_to_skill_02 = "/Users/bytedance/workspace/github/agentkit-samples/python/01-tutorials/04-agentkit-tools/genius_skills/agentkit_e2e_ops.txt"
    # 2. 生成的skill存储在本地以下路径：
    #     skills_save_path = "/Users/bytedance/workspace/github/agentkit-samples/python/01-tutorials/04-agentkit-tools/genius_skills/sample-ops-skills"
    # 3. 根据 sample-ops-skills 中 skills 的步骤，使用 playwright_tools 来操控浏览器执行任务。
    # """
    # messages = """
    # 根据本地路径 "/Users/bytedance/workspace/github/agentkit-samples/python/01-tutorials/04-agentkit-tools/genius_skills/sample-ops-skills" 中skills的步骤，使用 playwright_tools 来操控浏览器执行任务.
    # """
    messages = """
    根据sample-ops-skills 中google-youtube-playback的步骤，使用 playwright_tools 来操控浏览器执行任务.
    """
    response = await runner.run(messages=messages, session_id=session_id)
    print(f"response: {response}")


# using veadk web for debugging
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    asyncio.run(main())
    # agent_server_app.run(host="0.0.0.0", port=8000)
