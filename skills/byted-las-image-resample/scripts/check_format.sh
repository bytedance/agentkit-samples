#!/bin/bash
# ==============================================================================
# 图片格式预检查
# Usage: scripts/check_format.sh <file_path>
# ==============================================================================

FILE_PATH="$1"

if [ -z "$FILE_PATH" ]; then
  echo "❌ 错误: 请提供文件路径"
  exit 1
fi

# 获取文件扩展名并转小写
EXT=$(echo "$FILE_PATH" | awk -F. '{print tolower($NF)}')

# 允许的图片格式
ALLOWED_FORMATS="jpg jpeg png bmp tiff tif webp"

if [[ " $ALLOWED_FORMATS " =~ " $EXT " ]]; then
  echo "✅ 格式检查通过: $EXT"
  exit 0
else
  echo "⚠️  警告: 文件扩展名 '$EXT' 不在推荐格式列表中"
  echo "   推荐格式: $ALLOWED_FORMATS"
  echo "   请确认输入格式正确"
  exit 1
fi
