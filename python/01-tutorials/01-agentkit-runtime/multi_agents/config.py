import os

# 统一配置模型名称，优先使用环境变量，默认值为 deepseek-v3-2-251201
MODEL_NAME = os.getenv("MODEL_AGENT_NAME", "deepseek-v3-2-251201")
