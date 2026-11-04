#!/bin/bash

# 快速提交刷新任务脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 项目内置 bin/ve 是 macOS arm64 (Apple Silicon) 专用构建，仅在该平台使用；
# 其他平台(Intel macOS / Linux)改用 PATH 中的 ve，避免执行架构不兼容的二进制。
LOCAL_CLI="$PROJECT_DIR/bin/ve"
if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ] && [ -f "$LOCAL_CLI" ] && [ -x "$LOCAL_CLI" ]; then
    VE_CMD="$LOCAL_CLI"
elif command -v ve >/dev/null 2>&1; then
    VE_CMD="ve"
else
    echo "错误: 未找到兼容当前平台 ($(uname -s)/$(uname -m)) 的 ve CLI。" >&2
    echo "  项目内置 bin/ve 仅支持 macOS arm64；请按 $PROJECT_DIR/references/install-guide.md 安装对应版本。" >&2
    exit 1
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
