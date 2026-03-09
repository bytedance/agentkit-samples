#!/bin/bash
# Video Breakdown Agent 部署脚本

set -e

# 确保在项目根目录执行
if [ ! -f "agent.py" ]; then
  echo "请在 video_breakdown_agent 项目根目录执行此脚本"
  exit 1
fi

AGENT_NAME="video_breakdown_agent"
ENTRY_POINT="agent.py"

echo "🚀 配置 AgentKit 部署参数..."
agentkit config \
  --agent_name "${AGENT_NAME}" \
  --entry_point "${ENTRY_POINT}" \
  --launch_type cloud

echo "🔧 配置环境变量..."
agentkit config \
  -e DATABASE_TOS_BUCKET="${DATABASE_TOS_BUCKET:-video-breakdown-uploads}" \
  -e DATABASE_TOS_REGION="${DATABASE_TOS_REGION:-cn-beijing}" \
  -e FFMPEG_BIN="${FFMPEG_BIN:-ffmpeg}" \
  -e FFPROBE_BIN="${FFPROBE_BIN:-ffprobe}"

echo "✅ 配置完成。现在可以执行 'agentkit launch' 进行部署。"
echo ""
echo "注意事项："
echo "  1. 确保已配置 VOLCENGINE_ACCESS_KEY 和 VOLCENGINE_SECRET_KEY"
echo "  2. 确保 TOS 存储桶已创建"
echo "  3. FFmpeg 已通过 imageio-ffmpeg 打包在 Python 依赖中，无需单独安装"
echo "  4. 如需 ASR 功能，请配置 ASR_APP_ID 和 ASR_ACCESS_KEY"
