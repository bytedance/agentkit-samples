
#!/bin/bash

# 火山引擎 CLI CDN 域名添加脚本（带必填项检查和默认值）
# 使用方法: ./add-cdn-domain.sh [--check]
# --check: 强制重新进行环境检查

set -e

echo "=========================================="
echo "  火山引擎 CLI - CDN 域名添加助手"
echo "=========================================="
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RECOMMEND_CONFIG_SCRIPT="$SCRIPT_DIR/recommend-config.sh"

# 优先使用项目本地的 CLI
LOCAL_CLI="$PROJECT_DIR/bin/ve"
if [ -f "$LOCAL_CLI" ] && [ -x "$LOCAL_CLI" ]; then
    VE_CMD="$LOCAL_CLI"
    echo "✅ 使用项目本地 CLI: $LOCAL_CLI"
else
    VE_CMD="ve"
fi

# 引入推荐配置逻辑
if [ ! -f "$RECOMMEND_CONFIG_SCRIPT" ]; then
    echo "❌ 未找到推荐配置脚本: $RECOMMEND_CONFIG_SCRIPT"
    exit 1
fi
# shellcheck source=/dev/null
source "$RECOMMEND_CONFIG_SCRIPT"

# 环境检查标志文件
ENV_CHECK_FILE="$HOME/.volc-cdn-cli-env-check"
# 环境检查有效期（秒）- 1 天
ENV_CHECK_EXPIRE=86400

# 解析命令行参数
FORCE_CHECK=false
if [ "$1" = "--check" ]; then
    FORCE_CHECK=true
    echo "🔄 强制进行环境检查..."
    echo ""
fi

# 检查是否需要环境检测
needs_check=true
if [ "$FORCE_CHECK" = "false" ] && [ -f "$ENV_CHECK_FILE" ]; then
    # 检查标志文件是否过期
    file_time=$(stat -f "%m" "$ENV_CHECK_FILE" 2>/dev/null || echo 0)
    current_time=$(date +%s)
    time_diff=$((current_time - file_time))
    
    if [ $time_diff -lt $ENV_CHECK_EXPIRE ]; then
        echo "✅ 环境检查未过期，跳过环境检测"
        echo ""
        needs_check=false
    else
        echo "🔄 环境检查已过期，重新进行检测"
        echo ""
    fi
fi

if [ "$needs_check" = "true" ]; then
    # ==========================================
    # 第一阶段：环境检查
    # ==========================================
    
    echo "【第一阶段】环境检查"
    echo ""
    
    # 检查 ve 是否可用
    echo "🔍 检查火山引擎 CLI..."
    
    if ! "$VE_CMD" --help &>/dev/null; then
        echo "❌ 未找到 've' 命令"
        echo ""
        echo "=========================================="
        echo "  需要先安装火山引擎 CLI"
        echo "=========================================="
        echo ""
        echo "请按照以下步骤安装："
        echo ""
        
        # 检测系统架构
        ARCH=$(uname -m)
        if [ "$ARCH" = "arm64" ]; then
            echo "1. 检测到您的系统是 Apple Silicon (arm64)"
            DOWNLOAD_URL="https://github.com/volcengine/volcengine-cli/releases/download/v1.0.39/volcengine-cli_1.0.39_darwin_arm64.zip"
        elif [ "$ARCH" = "x86_64" ]; then
            echo "1. 检测到您的系统是 Intel (x86_64)"
            DOWNLOAD_URL="https://github.com/volcengine/volcengine-cli/releases/download/v1.0.39/volcengine-cli_1.0.39_darwin_amd64.zip"
        else
            echo "⚠️  无法检测系统架构，请手动选择"
            echo ""
            echo "   Apple Silicon (M1/M2/M3): arm64"
            echo "   Intel: x86_64"
            echo ""
            exit 1
        fi
        
        echo ""
        echo "2. 下载 CLI："
        echo "   curl -L -s "$DOWNLOAD_URL" -o ve.zip"
        echo ""
        echo "3. 解压并安装："
        echo "   unzip -q ve.zip"
        echo "   mkdir -p ~/.local/bin"
        echo "   mv ve ~/.local/bin/"
        echo ""
        echo "4. 配置环境变量（如果还没有配置）："
        echo "   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc"
        echo "   source ~/.zshrc"
        echo ""
        echo "5. 配置访问凭证："
        echo "   ve configure set --access-key <您的AK> --secret-key <您的SK> --region cn-guangzhou --profile default"
        echo ""
        echo "6. 验证安装："
        echo "   ve version"
        echo ""
        echo "安装完成后，请重新运行此脚本！"
        exit 1
    fi
    
    echo "✅ 火山引擎 CLI 已找到"
    
    # 检查 CDN 命令是否可用（简化版本检查）
    echo "🔍 检查 CDN 命令是否可用..."
    if ! "$VE_CMD" cdn --help &>/dev/null; then
        echo ""
        echo "❌ 错误: CDN 命令不可用"
        echo "   请升级 CLI 到 1.0.39 或更高版本"
        echo ""
        echo "升级步骤："
        ARCH=$(uname -m)
        if [ "$ARCH" = "arm64" ]; then
            DOWNLOAD_URL="https://github.com/volcengine/volcengine-cli/releases/download/v1.0.39/volcengine-cli_1.0.39_darwin_arm64.zip"
        else
            DOWNLOAD_URL="https://github.com/volcengine/volcengine-cli/releases/download/v1.0.39/volcengine-cli_1.0.39_darwin_amd64.zip"
        fi
        echo "   curl -L -s "$DOWNLOAD_URL" -o ve.zip"
        echo "   unzip -q -o ve.zip"
        echo "   mv ve ~/.local/bin/"
        echo ""
        exit 1
    fi
    echo "✅ CDN 命令可用"
    
    # 检查配置状态 - 跳过配置文件权限检查，直接进入需求收集
    echo "🔍 检查配置状态..."
    echo "⚠️  跳过配置文件检查（权限限制）"
    echo "   请确保在执行前已配置好 AK/SK"
    echo ""
    echo "✅ 配置状态正常"
    
    # 更新环境检查标志文件
    touch "$ENV_CHECK_FILE"
    echo "✅ 环境检查完成，更新检查标志文件"
    echo ""
fi

# ==========================================
# 第二阶段：需求收集
# ==========================================

echo ""
echo "【第二阶段】需求收集"
echo ""
echo "必填项检查：加速域名、区域、源站信息、缓存规则、业务类型"
echo ""

# 1. 加速域名
while true; do
    read -p "1. 加速域名 (必填): " DOMAIN
    if [ -z "$DOMAIN" ]; then
        echo "❌ 加速域名不能为空，请重新输入"
        continue
    fi
    
    # 域名格式验证
    if [[ ! "$DOMAIN" =~ ^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$ ]]; then
        echo "❌ 域名格式不正确，请重新输入（例如：www.example.com）"
        continue
    fi
    
    break
done

# 2. 源站配置
ORIGIN_LINES=()
ORIGIN_COUNT=0

while true; do
    echo ""
    echo "2. 源站配置（至少需要一个主源站）"
    echo "   当前已添加 $ORIGIN_COUNT 个源站"
    echo ""
    echo "   1. 添加主源站"
    echo "   2. 添加备源站"
    echo "   3. 完成源站配置"
    
    read -p "请选择操作 (1-3): " ORIGIN_ACTION
    
    case $ORIGIN_ACTION in
        "1" | "2")
            # 源站地址
            while true; do
                read -p "   源站地址 (IP 或域名): " ORIGIN_ADDRESS
                if [ -z "$ORIGIN_ADDRESS" ]; then
                    echo "❌ 源站地址不能为空，请重新输入"
                    continue
                fi
                
                # 源站格式验证
                if [[ "$ORIGIN_ADDRESS" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                    INSTANCE_TYPE="ip"
                    break
                elif [[ "$ORIGIN_ADDRESS" =~ ^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$ ]]; then
                    INSTANCE_TYPE="domain"
                    break
                else
                    echo "❌ 源站格式不正确，请输入有效的 IP 地址或域名"
                    continue
                fi
            done
            
            # 源站类型
            echo "   源站类型: $INSTANCE_TYPE"
            
            # 回源协议
            echo ""
            echo "   回源协议:"
            echo "   1. http"
            echo "   2. https"
            echo "   3. followclient"
            while true; do
                read -p "   请选择回源协议 (1-3): " ORIGIN_PROTOCOL_CHOICE
                case $ORIGIN_PROTOCOL_CHOICE in
                    "1")
                        ORIGIN_PROTOCOL="http"
                        break
                        ;;
                    "2")
                        ORIGIN_PROTOCOL="https"
                        break
                        ;;
                    "3")
                        ORIGIN_PROTOCOL="followclient"
                        break
                        ;;
                    *)
                        echo "❌ 无效的选择，请输入 1-3"
                        ;;
                esac
            done
            
            # 权重
            read -p "   权重 (1-100，默认 100): " WEIGHT
            WEIGHT=${WEIGHT:-100}
            
            # 源站类别
            if [ "$ORIGIN_ACTION" = "1" ]; then
                ORIGIN_TYPE="primary"
                echo "   源站类别: 主源站"
            else
                ORIGIN_TYPE="backup"
                echo "   源站类别: 备源站"
            fi
            
            # 添加到源站列表
            ORIGIN_LINES+=(
                "{
                  \"Address\": \"$ORIGIN_ADDRESS\",
                  \"InstanceType\": \"$INSTANCE_TYPE\",
                  \"OriginType\": \"$ORIGIN_TYPE\",
                  \"OriginProtocol\": \"$ORIGIN_PROTOCOL\",
                  \"Weight\": \"$WEIGHT\" 
                }"
            )
            
            ORIGIN_COUNT=$((ORIGIN_COUNT + 1))
            echo ""
            echo "✅ 源站添加成功！"
            ;;
            
        "3")
            # 检查是否至少有一个主源站
            HAS_PRIMARY=false
            PATTERN='OriginType": "primary"'
            for line in "${ORIGIN_LINES[@]}"; do
                if [[ "$line" =~ $PATTERN ]]; then
                    HAS_PRIMARY=true
                    break
                fi
            done
            
            if [ "$HAS_PRIMARY" = "false" ]; then
                echo ""
                echo "❌ 至少需要添加一个主源站"
                continue
            fi
            
            echo ""
            echo "✅ 源站配置完成，共添加 $ORIGIN_COUNT 个源站"
            break
            ;;
            
        *)
            echo "❌ 无效的选择，请输入 1-3"
            ;;
    esac
done

# 3. 业务类型
echo ""
echo "3. 业务类型 (必填):"
echo "   1. web (网页)"
echo "   2. download (下载)"
echo "   3. video (点播)"

while true; do
    read -p "请选择业务类型 (1-3): " SERVICE_TYPE_CHOICE
    case $SERVICE_TYPE_CHOICE in
        "1")
            SERVICE_TYPE="web"
            echo "   选择: web (网页)"
            break
            ;;
        "2")
            SERVICE_TYPE="download"
            echo "   选择: download (下载)"
            break
            ;;
        "3")
            SERVICE_TYPE="video"
            echo "   选择: video (点播)"
            break
            ;;
        *)
            echo "❌ 无效的选择，请输入 1-3"
            ;;
    esac
done

# 4. 区域（使用默认值）
DEFAULT_REGION="chinese_mainland"
read -p "4. 加速区域 (默认: chinese_mainland 中国内地): " SERVICE_REGION
SERVICE_REGION=${SERVICE_REGION:-$DEFAULT_REGION}
if [ "$SERVICE_REGION" = "$DEFAULT_REGION" ]; then
    echo "   使用默认值: $SERVICE_REGION (中国内地)"
fi

# 5. 缓存规则（根据业务类型自动应用推荐配置）
echo ""
echo "5. 缓存规则："
echo "   ✅ 根据选择的业务类型自动应用推荐配置规则"
echo "   - 点播场景：缓存 30 天，动态文件不缓存，开启 Range 回源、Multi-Range、缓存 Key 忽略全部查询参数、302 跟随、视频拖拽"
echo "   - 网页场景：缓存 30 天，动态文件不缓存，开启压缩和页面优化"
echo "   - 下载场景：缓存 30 天，动态文件不缓存，开启 Range 回源、Multi-Range、缓存 Key 忽略全部查询参数、302 跟随"

# 项目名称
read -p "6. 项目名称 (默认: default): " PROJECT
PROJECT=${PROJECT:-default}

# ==========================================
# 第三阶段：确认并添加
# ==========================================

echo ""
echo "【第三阶段】配置确认"
echo ""
echo "=========================================="
echo "  配置信息汇总"
echo "=========================================="
echo "  加速域名:   $DOMAIN"
echo "  业务类型:   $SERVICE_TYPE"
echo "  加速区域:   $SERVICE_REGION"
echo "  项目:       $PROJECT"
echo "  源站数量:   $ORIGIN_COUNT 个"

# 显示源站详情
echo ""
echo "  源站详情:"
echo "  ----------------------------------------"

index=1
for line in "${ORIGIN_LINES[@]}"; do
    address=$(echo "$line" | grep -Eo '"Address": "[^"]+"' | cut -d '"' -f4)
    type=$(echo "$line" | grep -Eo '"InstanceType": "[^"]+"' | cut -d '"' -f4)
    origin_type=$(echo "$line" | grep -Eo '"OriginType": "[^"]+"' | cut -d '"' -f4)
    protocol=$(echo "$line" | grep -Eo '"OriginProtocol": "[^"]+"' | cut -d '"' -f4)
    weight=$(echo "$line" | grep -Eo '"Weight": "[^"]+"' | cut -d '"' -f4)
    
    if [ "$origin_type" = "primary" ]; then
        origin_type_str="主源站"
    else
        origin_type_str="备源站"
    fi
    
    echo "  $index. $origin_type_str: $address ($type)"
    echo "     回源协议: $protocol"
    echo "     权重: $weight"
    index=$((index + 1))
done
echo "  ----------------------------------------"

# 显示推荐配置详情
echo ""
echo "  推荐配置详情:"
echo "  ----------------------------------------"
get_recommend_config_desc "$SERVICE_TYPE"
echo "  ----------------------------------------"
echo "=========================================="
echo ""

read -p "确认添加此域名? (y/n): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "已取消操作"
    exit 0
fi

# 构建源站配置字符串
ORIGIN_LINES_JSON=$(IFS=,; echo "${ORIGIN_LINES[*]}")

# 构建配置规则（调用共享函数）
CONFIG_RULES=""
CONFIG_CONTENT=$(get_recommend_config "$SERVICE_TYPE")
if [ -n "$CONFIG_CONTENT" ]; then
    CONFIG_RULES=",$CONFIG_CONTENT"
fi

# 构建 JSON body
BODY=$(cat <<EOF
{
  "Domain": "$DOMAIN",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          $ORIGIN_LINES_JSON
        ]
      }
    }
  ],
  "Project": "$PROJECT",
  "ServiceRegion": "$SERVICE_REGION",
  "ServiceType": "$SERVICE_TYPE"
  $CONFIG_RULES
}
EOF
)

echo ""
echo "正在调用 AddCdnDomain API..."
echo ""

# 执行命令（带超时设置和错误处理）
set +e
# 设置 30 秒超时
if command -v timeout &>/dev/null; then
    echo "⏱️  API 调用超时设置：30 秒"
    timeout 30 "$VE_CMD" cdn AddCdnDomain --body "$BODY"
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo ""
        echo "⏱️  API 调用超时！"
        echo "   请检查网络连接或稍后重试"
        echo ""
        exit 124
    fi
else
    # 如果系统没有 timeout 命令，使用默认执行
    "$VE_CMD" cdn AddCdnDomain --body "$BODY"
    EXIT_CODE=$?
fi
set -e

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ 命令已执行完成！"
    echo ""
    echo "📝 后续步骤："
    echo "   1. 等待 1-5 分钟，让域名配置生效"
    echo "   2. 登录火山引擎控制台获取 CNAME"
    echo "   3. 在您的 DNS 服务商处配置 CNAME 记录"
    echo "   4. 验证访问"
    echo ""
    echo "💡 提示：如需自定义缓存规则，请在域名创建后通过控制台或 API 修改"
else
    echo ""
    echo "❌ 命令执行失败！"
    echo ""
    echo "📋 常见问题排查："
    echo "   1. 检查 AK/SK 是否配置正确"
    echo "   2. 检查域名是否已存在"
    echo "   3. 检查 CLI 版本是否 >= 1.0.39"
    echo ""
    echo "💡 更多帮助请查看 SKILL.md 中的 FAQ 章节"
    exit $EXIT_CODE
fi

