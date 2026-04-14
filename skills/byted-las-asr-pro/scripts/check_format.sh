#!/bin/bash
# ==============================================================================
# 音频格式预检查
# Usage: scripts/check_format.sh <file_path>
# ==============================================================================

FILE_PATH="$1"

if [ -z "$FILE_PATH" ]; then
  echo "❌ 错误: 请提供文件路径"
  exit 1
fi

# 获取文件扩展名并转小写
EXT=$(echo "$FILE_PATH" | awk -F. '{print tolower($NF)}')

# 允许的容器格式
ALLOWED_FORMATS="wav mp3 m4a flac aac ogg"

if [[ " $ALLOWED_FORMATS " =~ " $EXT " ]]; then
  echo "✅ 格式检查通过: $EXT (容器格式)"
  exit 0
else
  echo "⚠️  警告: 文件扩展名 '$EXT' 可能不是容器格式"
  echo "   允许的容器格式: $ALLOWED_FORMATS"
  echo "   请确认 audio.format 参数是否正确"
  exit 1
fi
