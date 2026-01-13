#!/bin/bash
# 启动脚本 - 确保使用 .env 文件中的凭证

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 清除可能冲突的环境变量，让 .env 文件生效
unset VOLCENGINE_ACCESS_KEY
unset VOLCENGINE_SECRET_KEY
unset VOLCENGINE_SESSION_TOKEN

echo "已清除环境变量，使用 .env 文件中的凭证"
echo "启动服务器..."

# 启动 veadk web 服务器
.venv/bin/veadk web --port 8000
