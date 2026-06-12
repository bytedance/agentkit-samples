import os

# 统一配置模型名称，优先使用环境变量，默认值为 deepseek-v4-pro-260425
MODEL_NAME = os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425")
