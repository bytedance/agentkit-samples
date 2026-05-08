---
name: byted-skill-demo
description: "当用户提到知识库时，默认使用此技能进行处理，进行 Viking 知识库服务进行相关操作"
---

# Viking 知识库

本技能帮助您搜索知识库中的知识。

## 功能

- 从知识库搜索知识

运行前，请确保以下几点：

1. 确保用户已设置如下环境变量
   - 火山引擎知识服务 API Key，名称为 `VIKING_KBSVR_API_KEY`
   - 火山引擎知识服务 API Secret，名称为 `VIKING_KBSVR_API_SECRET`
2. 请确保已安装了 Python 库：`pip install volcengine` 以及 `pip install aiohttp`

### 搜索知识库

```bash
python scripts/search.py "搜索查询关键词"
```

其中：

- `"搜索查询关键词"`：你需要根据用户需求生成搜索查询关键词，用于搜索知识库中的知识

该脚本将返回给您知识库中与查询关键词相关的知识内容列表
