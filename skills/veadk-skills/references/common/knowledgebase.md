# 知识库

本文档介绍如何在 VeADK 中使用知识库。

## 导入

```python
from veadk.knowledgebase import KnowledgeBase
```

## 定义

通过 `KnowledgeBase` 类可以定义一个知识库，并挂载到智能体上。

```python
from veadk.knowledgebase import KnowledgeBase

# 定义知识库
knowledgebase = KnowledgeBase(
    name="my_knowledgebase",
    description="A knowledge base about ...",
    backend="viking",
    index=app_name,
    top_k=10,
)

agent = Agent(knowledgebase=knowledgebase)
```
