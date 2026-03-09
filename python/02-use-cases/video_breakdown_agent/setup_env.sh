#!/bin/bash
# Video Breakdown Agent 环境配置辅助脚本

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🔧 Video Breakdown Agent 环境配置向导"
echo "========================================"
echo ""

# 检查 .env 文件是否已存在
if [ -f ".env" ]; then
    echo "⚠️  检测到现有 .env 文件"
    read -p "是否要覆盖? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 已取消，保留现有配置"
        exit 0
    fi
fi

# 复制模板
if [ ! -f ".env.example" ]; then
    echo "❌ 错误：找不到 .env.example 模板文件"
    exit 1
fi

cp .env.example .env
echo "✅ 已创建 .env 文件（从 .env.example 复制）"
echo ""

# 引导用户填写必需变量
echo "📝 请填写以下必需的环境变量："
echo "----------------------------------------"
echo ""

# MODEL_AGENT_API_KEY
echo "1️⃣  火山方舟模型 API Key"
echo "   获取地址：https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey"
read -p "   输入 MODEL_AGENT_API_KEY: " MODEL_AGENT_API_KEY
if [ -n "$MODEL_AGENT_API_KEY" ]; then
    sed -i '' "s|^MODEL_AGENT_API_KEY=.*|MODEL_AGENT_API_KEY=$MODEL_AGENT_API_KEY|" .env
    echo "   ✅ 已保存"
fi
echo ""

# VOLCENGINE_ACCESS_KEY
echo "2️⃣  火山引擎访问密钥"
echo "   获取地址：https://console.volcengine.com/iam/keymanage/"
read -p "   输入 VOLCENGINE_ACCESS_KEY: " VOLCENGINE_ACCESS_KEY
if [ -n "$VOLCENGINE_ACCESS_KEY" ]; then
    sed -i '' "s|^VOLCENGINE_ACCESS_KEY=.*|VOLCENGINE_ACCESS_KEY=$VOLCENGINE_ACCESS_KEY|" .env
    echo "   ✅ 已保存"
fi
echo ""

# VOLCENGINE_SECRET_KEY
read -p "   输入 VOLCENGINE_SECRET_KEY: " VOLCENGINE_SECRET_KEY
if [ -n "$VOLCENGINE_SECRET_KEY" ]; then
    sed -i '' "s|^VOLCENGINE_SECRET_KEY=.*|VOLCENGINE_SECRET_KEY=$VOLCENGINE_SECRET_KEY|" .env
    echo "   ✅ 已保存"
fi
echo ""

# TOS Bucket
echo "3️⃣  TOS 存储桶配置"
echo "   创建地址：https://console.volcengine.com/tos/bucket"
read -p "   输入 DATABASE_TOS_BUCKET (默认: video-breakdown-uploads): " DATABASE_TOS_BUCKET
if [ -n "$DATABASE_TOS_BUCKET" ]; then
    sed -i '' "s|^DATABASE_TOS_BUCKET=.*|DATABASE_TOS_BUCKET=$DATABASE_TOS_BUCKET|" .env
    echo "   ✅ 已保存"
fi
echo ""

echo "========================================"
echo "✅ 环境配置完成！"
echo ""
echo "📋 下一步操作："
echo "   1. 本地测试：uv run veadk web"
echo "   2. 云端部署：agentkit launch"
echo ""
echo "💡 提示："
echo "   - 完整配置请编辑 .env 文件"
echo "   - 云端部署需在 AgentKit 控制台配置相同的环境变量"
echo "   - 参考文档：README.md"
echo ""
