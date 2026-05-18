#!/bin/bash

# 快速添加域名脚本（支持推荐配置）

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VE_CMD="$PROJECT_DIR/bin/ve"
RECOMMEND_CONFIG_SCRIPT="$SCRIPT_DIR/recommend-config.sh"

if [ ! -f "$VE_CMD" ] || [ ! -x "$VE_CMD" ]; then
    echo "❌ 未找到 CLI: $VE_CMD"
    exit 1
fi

# 引入推荐配置逻辑
if [ ! -f "$RECOMMEND_CONFIG_SCRIPT" ]; then
    echo "❌ 未找到推荐配置脚本: $RECOMMEND_CONFIG_SCRIPT"
    exit 1
fi
# shellcheck source=/dev/null
source "$RECOMMEND_CONFIG_SCRIPT"

echo "✅ 使用系统配置的 AK/SK"
echo ""

# 默认配置
DOMAIN="${1:-example-domain.com}"
ORIGIN1="${2:-1.1.1.1}"
ORIGIN2="${3:-}"
ORIGIN3="${4:-}"
WEIGHT1="${5:-100}"
WEIGHT2="${6:-100}"
WEIGHT3="${7:-100}"
SERVICE_TYPE="${8:-web}"

# 构建源站配置
ORIGIN_LINES=""

# 主源 1
ORIGIN_LINES+="{
            \"Address\": \"$ORIGIN1\",
            \"InstanceType\": \"ip\",
            \"OriginType\": \"primary\",
            \"OriginProtocol\": \"https\",
            \"Weight\": \"$WEIGHT1\"
          }"

# 主源 2（可选）
if [ -n "$ORIGIN2" ]; then
    ORIGIN_LINES+=",
          {
            \"Address\": \"$ORIGIN2\",
            \"InstanceType\": \"ip\",
            \"OriginType\": \"primary\",
            \"OriginProtocol\": \"https\",
            \"Weight\": \"$WEIGHT2\"
          }"
fi

# 备源（可选）
if [ -n "$ORIGIN3" ]; then
    ORIGIN_LINES+=",
          {
            \"Address\": \"$ORIGIN3\",
            \"InstanceType\": \"domain\",
            \"OriginType\": \"backup\",
            \"OriginProtocol\": \"https\",
            \"Weight\": \"$WEIGHT3\"
          }"
fi

# 构建推荐配置（调用共享函数）
RECOMMEND_CONFIG=""
CONFIG_CONTENT=$(get_recommend_config "$SERVICE_TYPE")
if [ -n "$CONFIG_CONTENT" ]; then
    RECOMMEND_CONFIG=",$CONFIG_CONTENT"
fi

# 构建 JSON
BODY=$(cat <<EOF
{
  "Domain": "$DOMAIN",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          $ORIGIN_LINES
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "$SERVICE_TYPE"
  $RECOMMEND_CONFIG
}
EOF
)

echo "=== 配置信息 ==="
echo "域名: $DOMAIN"
echo "主源1: $ORIGIN1, 权重$WEIGHT1"
if [ -n "$ORIGIN2" ]; then
    echo "主源2: $ORIGIN2, 权重$WEIGHT2"
fi
if [ -n "$ORIGIN3" ]; then
    echo "备源: $ORIGIN3, 权重$WEIGHT3"
fi
echo "业务类型: $SERVICE_TYPE"
echo "推荐配置: 已启用"
echo ""
echo "=== 执行 ==="

# 执行命令（带超时）
echo "正在调用 AddCdnDomain API（超时时间：30 秒）..."
echo ""

# 检测系统是否支持 timeout 命令
if command -v timeout >/dev/null 2>&1; then
    # 使用 timeout 命令
    timeout 30 VOLCENGINE_REGION="cn-guangzhou" "$VE_CMD" cdn AddCdnDomain --body "$BODY"
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 124 ]; then
        echo ""
        echo "❌ API 调用超时（30 秒）"
        echo "💡 建议："
        echo "   1. 检查网络连接是否正常"
        echo "   2. 稍后重试"
        exit 124
    fi
else
    # 不支持 timeout，直接执行
    echo "⚠️  系统不支持 timeout 命令，无超时保护"
    VOLCENGINE_REGION="cn-guangzhou" "$VE_CMD" cdn AddCdnDomain --body "$BODY"
fi
