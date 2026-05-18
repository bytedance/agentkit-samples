#!/bin/bash

# 快速提交预热任务脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 优先使用项目本地的 CLI
LOCAL_CLI="$PROJECT_DIR/bin/ve"
if [ -f "$LOCAL_CLI" ] && [ -x "$LOCAL_CLI" ]; then
    VE_CMD="$LOCAL_CLI"
else
    VE_CMD="ve"
fi

if [ $# -eq 0 ]; then
    echo "使用方法: $0 <url1> <url2> ..."
    echo ""
    echo "示例: $0 https://www.example.com/1.jpg https://www.example.com/2.jpg"
    exit 1
fi

# 构建URL列表
urls=("$@")
url_list=$(printf '"%s",' "${urls[@]}")
url_list=${url_list%,}
body="{\"UrlList\":[$url_list]}"

echo "=== 预热任务 ==="
echo "URL数量: ${#urls[@]}"
echo "URL列表:"
for url in "${urls[@]}"; do
    echo "  - $url"
done
echo ""
echo "正在提交..."
echo ""

VOLCENGINE_REGION="cn-guangzhou" "$VE_CMD" cdn SubmitPreloadTask --body "$body"
