# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""A VeADK code agent that uses an AgentKit Sandbox session with EFS."""

from __future__ import annotations

import os

from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner

from efs_workspace import run_efs_workspace_demo


def _is_byteplus() -> bool:
    provider = os.getenv("CLOUD_PROVIDER", "").strip().lower()
    return provider == "byteplus" or (
        not provider and bool(os.getenv("BYTEPLUS_REGION"))
    )


DEFAULT_MODEL_AGENT_NAME = (
    "deepseek-v4-1-flash-260910" if _is_byteplus() else "doubao-seed-evolving"
)

root_agent = Agent(
    name="efs_code_workspace_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", DEFAULT_MODEL_AGENT_NAME),
    description=(
        "一个会创建多个 EFS 挂载沙箱、生成代码产物并验证跨实例共享的代码智能体"
    ),
    instruction="""你是一个代码智能体示例，重点演示 AgentKit Sandbox 与 EFS 的配套使用链路。

当用户要求演示 EFS、跨实例工作区、FilespaceName 隔离、代码产物保存或完整链路验证时，必须调用
`run_efs_workspace_demo` 工具。工具会先创建 writer Sandbox Session 并挂载指定 EFS filespace，
在 EFS 路径下写入任务、报告、元数据和可执行校验脚本；随后创建 reader Sandbox Session，挂载
同一个 FilespaceName 并执行 writer 留下的脚本，证明目录和文件来自共享 EFS。如果配置了第二个
FilespaceName，工具还会创建 isolation Session 做同路径不可见的反向校验。

除非用户明确要求保留沙箱用于排查，否则调用工具时保持 cleanup=true，避免遗留会话。最终回答用
中文说明 writer/reader Session、EFS 挂载路径、生成了哪些文件、reader 执行了哪个共享脚本，
以及同 FilespaceName 共享和可选隔离校验的结论。
如果工具返回 ok=false，不要编造成功结果，直接说明缺少的环境变量、权限或下游错误。""",
    tools=[run_efs_workspace_demo],
)

runner = Runner(agent=root_agent, app_name="efs_code_workspace_agent")

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
)


if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
