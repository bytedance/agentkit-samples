from veadk import Agent, Runner
from veadk.tools.builtin_tools.execute_skills import execute_skills
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid


async def main(prompts: list[tuple[str, str]]) -> list[str]:
    """Runs agent tasks in parallel using a thread pool."""
    agent = Agent(
        name="skill_agent",
        instruction="根据用户的需求，调用 execute_skills 工具执行 skills，",
        tools=[execute_skills],
    )
    runner = Runner(agent=agent)

    def run_in_event_loop(prompt, session_id):
        return asyncio.run(runner.run(messages=prompt, session_id=session_id))

    with ThreadPoolExecutor() as executor:
        tasks = [
            executor.submit(run_in_event_loop, prompt, session_id)
            for prompt, session_id in prompts
        ]
        results = [task.result() for task in tasks]

    return results


if __name__ == "__main__":
    your_account_id = "YOUR_ACCOUNT_ID"
    your_bucket_name = f"agentkit-platform-{your_account_id}"
    user_input = """
        使用 internal-comms skill 帮我写一个3p沟通材料，通知3p团队项目进度更新。关于产品团队，主要包括过去一周问题和未来一周计划，具体包括问题：写产品团队遇到的客户问题 (1. GPU+模型推理框架性能低于开源版本，比如时延高、吞吐低；2. GPU推理工具易用性差)，以及如何解决的；计划：明年如何规划GPU产品功能和性能优化 (1. 发力GPU基础设施对生图生视频模型的支持；2. GPU推理相关工具链路易用性提升)。其他内容，可以酌情组织。
    """

    user_inputs = [user_input, user_input, user_input]
    session_ids = [str(uuid.uuid4()) for _ in user_inputs]
    prompts_with_sessions = list(zip(user_inputs, session_ids))

    responses = asyncio.run(main(prompts_with_sessions))
    for response in responses:
        print(response)
