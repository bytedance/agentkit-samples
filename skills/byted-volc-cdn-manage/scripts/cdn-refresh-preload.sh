#!/bin/bash

# 火山引擎 CLI CDN 刷新预热管理脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 优先使用项目本地的 CLI
LOCAL_CLI="$PROJECT_DIR/bin/ve"
if [ -f "$LOCAL_CLI" ] && [ -x "$LOCAL_CLI" ]; then
    VE_CMD="$LOCAL_CLI"
    echo "✅ 使用项目本地 CLI: $LOCAL_CLI"
else
    VE_CMD="ve"
fi

echo "=========================================="
echo "  火山引擎 CLI - CDN 刷新预热管理"
echo "=========================================="
echo ""

# 检查 CLI 是否可用
if ! "$VE_CMD" --help &>/dev/null; then
    echo "❌ 未找到 've' 命令"
    echo ""
    echo "请先安装火山引擎 CLI，参考: $PROJECT_DIR/references/install-guide.md"
    exit 1
fi

# 菜单选择
echo "请选择要执行的操作："
echo "1. 提交预热任务"
echo "2. 提交刷新任务"
echo ""
read -p "请输入选项 (1/2): " choice

case $choice in
    1)
        echo ""
        echo "=== 提交预热任务 ==="
        echo ""
        echo "请输入要预热的URL列表（每行一个URL，输入空行结束）："
        urls=()
        while true; do
            read -p "URL: " url
            if [ -z "$url" ]; then
                break
            fi
            urls+=("$url")
        done

        if [ ${#urls[@]} -eq 0 ]; then
            echo "❌ 未输入任何URL"
            exit 1
        fi

        # 构建JSON
        url_list=$(printf '"%s",' "${urls[@]}")
        url_list=${url_list%,}
        body="{\"UrlList\":[$url_list]}"

        echo ""
        echo "=== 确认信息 ==="
        echo "操作类型: 预热"
        echo "URL数量: ${#urls[@]}"
        echo "URL列表:"
        for url in "${urls[@]}"; do
            echo "  - $url"
        done
        echo ""
        echo "请求内容: $body"
        echo ""

        read -p "确认提交? (y/n): " confirm
        if [ "$confirm" != "y" ]; then
            echo "已取消"
            exit 0
        fi

        echo ""
        echo "正在提交预热任务..."
        echo ""

        VOLCENGINE_REGION="cn-guangzhou" "$VE_CMD" cdn SubmitPreloadTask --body "$body"
        ;;

    2)
        echo ""
        echo "=== 提交刷新任务 ==="
        echo ""
        echo "请选择刷新类型："
        echo "1. file（文件刷新）"
        echo "2. directory（目录刷新）"
        echo ""
        read -p "请输入选项 (1/2, 默认 1): " type_choice

        case $type_choice in
            2)
                refresh_type="directory"
                ;;
            *)
                refresh_type="file"
                ;;
        esac

        echo ""
        echo "请输入要刷新的URL列表（每行一个URL，输入空行结束）："
        urls=()
        while true; do
            read -p "URL: " url
            if [ -z "$url" ]; then
                break
            fi
            urls+=("$url")
        done

        if [ ${#urls[@]} -eq 0 ]; then
            echo "❌ 未输入任何URL"
            exit 1
        fi

        # 构建JSON
        url_list=$(printf '"%s",' "${urls[@]}")
        url_list=${url_list%,}
        body="{\"Type\":\"$refresh_type\",\"UrlList\":[$url_list]}"

        echo ""
        echo "=== 确认信息 ==="
        echo "操作类型: 刷新"
        echo "刷新类型: $refresh_type"
        echo "URL数量: ${#urls[@]}"
        echo "URL列表:"
        for url in "${urls[@]}"; do
            echo "  - $url"
        done
        echo ""
        echo "请求内容: $body"
        echo ""

        read -p "确认提交? (y/n): " confirm
        if [ "$confirm" != "y" ]; then
            echo "已取消"
            exit 0
        fi

        echo ""
        echo "正在提交刷新任务..."
        echo ""

        VOLCENGINE_REGION="cn-guangzhou" "$VE_CMD" cdn SubmitRefreshTask --body "$body"
        ;;

    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac

echo ""
echo "✅ 任务提交完成！"
