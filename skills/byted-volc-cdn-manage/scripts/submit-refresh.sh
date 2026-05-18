#!/bin/bash

# 快速提交刷新任务脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 优先使用项目本地的 CLI
LOCAL_CLI="$PROJECT_DIR/bin/ve"
if [ -f "$LOCAL_CLI" ] && [ -x "$LOCAL_CLI" ]; then
    VE_CMD="$LOCAL_CLI"
else
    VE_CMD="ve"
fi

# 解析参数
refresh_type="file"
urls=()

while [ $# -gt 0 ]; do
    case $1 in
        --type|-t)
            refresh_type="$2"
            shift 2
            ;;
        *)
            urls+=("$1")
            shift
            ;;
    esac
done

if [ ${#urls[@]} -eq 0 ]; then
    echo "使用方法: $0 [--type <file|directory>] <url1> <url2> ..."
    echo ""
    echo "示例:"
    echo "  $0 https://www.example.com/1.jpg https://www.example.com/2.jpg"
    echo "  $0 --type directory https://www.example.com/path/"
    exit 1
fi

# 构建URL列表 - JSON数组
url_list=$(printf '"%s",' "${urls[@]}")
url_list=${url_list%,}
body="{\"Type\":\"$refresh_type\",\"UrlList\":[$url_list]}"

echo "=== 刷新任务 ==="
echo "刷新类型: $refresh_type"
echo "URL数量: ${#urls[@]}"
echo "URL列表:"
for url in "${urls[@]}"; do
    echo "  - $url"
done
echo ""
echo "正在提交..."
echo ""

VOLCENGINE_REGION="cn-guangzhou" "$VE_CMD" cdn SubmitRefreshTask --body "$body"
