#!/bin/bash
# ==============================================================================
# 音频/视频容器格式预检查
# Usage: scripts/check_format.sh <file_path>
# ==============================================================================

FILE_PATH="$1"
if [ -z "$FILE_PATH" ]; then
  echo "❌ 错误: 请提供文件路径"
  exit 1
fi

EXT=$(echo "$FILE_PATH" | awk -F. '{print tolower($NF)}')
ALLOWED_FORMATS="wav mp3 m4a flac aac mp4 avi mkv mov ogg"

if [[ " $ALLOWED_FORMATS " =~ " $EXT " ]]; then
  echo "✅ 格式检查通过: $EXT"
  exit 0
fi

echo "⚠️  警告: 文件扩展名 '$EXT' 不在推荐列表中"
echo "   推荐格式: $ALLOWED_FORMATS"
exit 1
