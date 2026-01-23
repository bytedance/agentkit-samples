# Agent 定义方法

## 导入方法

- LLM Agent: `from veadk import Agent`
- Sequential Agent: `from veadk.agents.sequential_agent import SequentialAgent`
- Loop Agent: `from veadk.agents.loop_agent import LoopAgent`

其中，LLM Agent 是最基础的智能体（由 LLM 启动进行自主决策），Sequential Agent 是按顺序执行的智能体，Loop Agent 是循环执行的智能体。

## 代码规范

你可以通过如下方式定义智能体：

```python
root_agent = Agent(
    name="...",
    description="...",
    instruction="...", # 智能体系统提示词
    sub_agents=[sub_agent] # 子智能体列表
)

sub_agent = Agent(
    name="...",
    description="...",
    instruction="...", # 智能体系统提示词
)
```

你也可以生成一个强制按顺序执行的智能体：

```python
sub_agent_1 = Agent(
    name="...",
    description="...",
    instruction="...", # 智能体系统提示词
)

sub_agent_2 = Agent(
    name="...",
    description="...",
    instruction="...", # 智能体系统提示词
)

# SequentialAgent 只需要写入 sub_agent 即可
root_agent = SequentialAgent(
    sub_agents=[sub_agent_1, sub_agent_2] # 子智能体列表
)
```

`sub_agent_1` 与 `sub_agent_2` 将会严格按顺序执行

注意，根智能体的命名必须为 `root_agent`。

## 让 Agent 结构化输出

为保证更高的准确率和 Agent 执行时的可控性，使用结构化输出是一种有效的手段。

在定义 Agent 时，通过 `model_extra_config={"response_format": ...}` 可以让 Agent 结构化输出。其中，`...` 是你定义的 Pydantic 模型，用于描述 Agent 的输出格式。

```python
from pydantic import BaseModel
from veadk import Agent, Runner


# 定义分步解析模型（对应业务场景的结构化响应）
class Step(BaseModel):
    explanation: str  # 步骤说明
    output: str  # 步骤计算结果


# 定义最终响应模型（包含分步过程和最终答案）
class MathResponse(BaseModel):
    steps: list[Step]  # 解题步骤列表
    final_answer: str  # 最终答案


agent = Agent(
    instruction="你是一位数学辅导老师，需详细展示解题步骤",
    model_extra_config={"response_format": MathResponse},
)
```
