#!/bin/bash

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# OpenClaw 自动备份脚本
# 功能：备份核心配置、技能文件和记忆数据到TOS网盘，按日期分类存储

set -euo pipefail

# 配置项
WORKSPACE_DIR="/root/.openclaw/workspace"
CONFIG_DIR="/root/.openclaw"
EXTENSIONS_DIR="/root/.openclaw/extensions"
SKILLS_DIR="/root/.openclaw/workspace/skills"
MEMORY_DIR="/root/.openclaw/workspace/memory"
BACKUP_ROOT="openclaw_backup"
DATE=$(date +%Y-%m-%d)

# 检测挂载的网盘
echo "🔍 检测可用网盘..."
MOUNT_ROOT="/root/.openclaw/workspace"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../.config"

# 读取配置文件（如果存在）
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
    if [ -n "${DEFAULT_BUCKET:-}" ] && [ -n "${MOUNT_POINT:-}" ]; then
        # 验证配置的挂载点是否仍然有效
        if df -P | grep -q "^.* $MOUNT_POINT$"; then
            BUCKET_NAME="$DEFAULT_BUCKET"
            echo "✅ 使用配置的默认存储桶: $BUCKET_NAME ($MOUNT_POINT)"
        else
            echo "⚠️  配置的存储桶 $DEFAULT_BUCKET 已失效，重新检测可用存储桶"
            unset DEFAULT_BUCKET
            unset MOUNT_POINT
        fi
    fi
fi

# 如果没有有效的配置，自动检测
if [ -z "${MOUNT_POINT:-}" ]; then
    # 检测所有挂载的网盘
    mounts=$(df -P | grep "$MOUNT_ROOT" | awk '{print $NF}')

    if [ -z "$mounts" ]; then
        echo "❌ 未检测到挂载的网盘，请先在arkClaw界面配置TOS存储桶"
        exit 1
    fi

    # 选择第一个可用的挂载点
    MOUNT_POINT=$(echo "$mounts" | head -n 1)
    BUCKET_NAME=$(basename "$MOUNT_POINT")

    echo "✅ 自动选择存储桶: $BUCKET_NAME ($MOUNT_POINT)"
    echo "ℹ️  所有可用存储桶:"
    echo "$mounts" | while read -r mp; do
        echo "  - $(basename "$mp"): $mp"
    done
    echo "💡 如需固定使用某个存储桶，请运行: bash scripts/config.sh <存储桶名称>"
fi

BACKUP_DIR="$MOUNT_POINT/$BACKUP_ROOT/$DATE"

# 创建备份目录
echo -e "\n📂 创建备份目录: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# 备份核心配置文件
echo -e "\n📝 备份核心配置文件 (MD文档)..."
shopt -s nullglob
md_files=("$WORKSPACE_DIR"/*.md)
if [ ${#md_files[@]} -gt 0 ]; then
    cp "${md_files[@]}" "$BACKUP_DIR/"
    echo "✅ 核心配置文件备份完成 (${#md_files[@]} 个文件)"
else
    echo "ℹ️  无核心配置文件需要备份"
fi
shopt -u nullglob

# 备份系统配置
echo -e "\n⚙️  备份系统配置 (仅配置文件，跳过二进制)..."
mkdir -p "$BACKUP_DIR/config"
if [ -d "$CONFIG_DIR" ]; then
    config_count=0
    mkdir -p "$BACKUP_DIR/config"
    
    # 备份根目录配置文件
    root_configs=$(find "$CONFIG_DIR" -maxdepth 1 -type f \( -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.conf" -o -name "*.env" -o -name "*.ini" -o -name "*.md" \))
    root_count=$(echo "$root_configs" | grep -v '^$' | wc -l)
    if [ "$root_count" -gt 0 ]; then
        echo "$root_configs" | xargs cp -t "$BACKUP_DIR/config/"
        config_count=$((config_count + root_count))
    fi
    
    # 遍历所有子目录，智能备份
    echo "🔍 扫描系统配置子目录..."
    for dir in "$CONFIG_DIR"/*/; do
        dir_name=$(basename "$dir")
        # 跳过不需要备份的大体积目录
        if [[ "$dir_name" == "node_modules" || "$dir_name" == "venv" || "$dir_name" == "__pycache__" || "$dir_name" == "dist" || "$dir_name" == "build" || "$dir_name" == "logs" || "$dir_name" == "workspace" ]]; then
            echo "⚠️  跳过目录: $dir_name (排除列表)"
            continue
        fi
        
        # 计算目录大小和文件数
        dir_size=$(du -sh "$dir" | cut -f1)
        file_count=$(find "$dir" -type f | wc -l)
        
        # 智能判断是否备份：小于100MB且文件数少于1000个
        size_num=$(echo "$dir_size" | sed 's/[MKG]//')
        size_unit=$(echo "$dir_size" | sed 's/[0-9.]//g')
        
        skip=false
        if [[ "$size_unit" == "G" ]]; then
            skip=true
        elif [[ "$size_unit" == "M" && $(echo "$size_num > 100" | bc -l) -eq 1 ]]; then
            skip=true
        elif [[ "$file_count" -gt 1000 ]]; then
            skip=true
        fi
        
        if [ "$skip" = true ]; then
            echo "⚠️  跳过目录: $dir_name (大小: $dir_size, 文件数: $file_count - 超过阈值)"
            continue
        fi
        
        # 备份目录
        echo "✅ 备份目录: $dir_name (大小: $dir_size, 文件数: $file_count)"
        mkdir -p "$BACKUP_DIR/config/$dir_name"
        cp -r "$dir"/* "$BACKUP_DIR/config/$dir_name/" 2>/dev/null
        config_count=$((config_count + file_count))
    done
    
    if [ "$config_count" -gt 0 ]; then
        echo "✅ 系统配置备份完成 ($config_count 个文件)"
    else
        echo "ℹ️  无系统配置文件需要备份"
    fi
else
    echo "ℹ️  系统配置目录不存在，跳过系统配置备份"
fi

# 备份技能文件
echo -e "\n🔧 备份技能文件 (仅源码文件，跳过node_modules等依赖目录)..."
mkdir -p "$BACKUP_DIR/skills/extensions"
mkdir -p "$BACKUP_DIR/skills/workspace"

# 备份扩展技能
find "$EXTENSIONS_DIR" -type f \( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.md" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.sh" -o -name "*.html" -o -name "*.css" \) \
  -not -path "*/node_modules/*" \
  -not -path "*/venv/*" \
  -not -path "*/__pycache__/*" \
  -not -path "*/dist/*" \
  -not -path "*/build/*" \
  -not -path "*/.git/*" \
  -exec cp --parents {} "$BACKUP_DIR/skills/extensions/" \; 2>/dev/null

# 备份工作区技能
find "$SKILLS_DIR" -type f \( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.md" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.sh" -o -name "*.html" -o -name "*.css" \) \
  -not -path "*/node_modules/*" \
  -not -path "*/venv/*" \
  -not -path "*/__pycache__/*" \
  -not -path "*/dist/*" \
  -not -path "*/build/*" \
  -not -path "*/.git/*" \
  -exec cp --parents {} "$BACKUP_DIR/skills/workspace/" \; 2>/dev/null

echo "✅ 技能文件备份完成"

# 备份记忆数据
echo -e "\n🧠 备份记忆数据..."
mkdir -p "$BACKUP_DIR/memory"
if [ -d "$MEMORY_DIR" ]; then
    cp -r "$MEMORY_DIR"/* "$BACKUP_DIR/memory/" 2>/dev/null || echo "ℹ️  无记忆数据需要备份"
else
    echo "ℹ️  记忆目录不存在，跳过记忆数据备份"
fi
echo "✅ 记忆数据备份完成"

# 生成备份统计
echo -e "\n📊 生成备份统计..."
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "计算中")
FILE_COUNT=$(find "$BACKUP_DIR" -type f 2>/dev/null | wc -l || echo "0")

# 生成备份摘要
SUMMARY_PATH="$BACKUP_DIR/backup_summary.txt"
cat > "$SUMMARY_PATH" << EOF
✅ 备份完成！
📦 备份桶: $BUCKET_NAME
📂 备份路径: $BACKUP_ROOT/$DATE
📄 备份文件数: $FILE_COUNT
💾 总大小: $BACKUP_SIZE
📅 备份时间: $(date '+%Y-%m-%d %H:%M:%S')
EOF

# 生成完整文件清单
MANIFEST_PATH="$BACKUP_DIR/backup_manifest.txt"
find "$BACKUP_DIR" -type f -exec ls -lh {} \; > "$MANIFEST_PATH" 2>/dev/null || true

# 输出结果
echo -e "\n✅ 备份完成！"
echo "📦 备份桶: $BUCKET_NAME"
echo "📂 备份路径: $BACKUP_ROOT/$DATE"
echo "📄 备份文件数: $FILE_COUNT"
echo "💾 总大小: $BACKUP_SIZE"
echo -e "\n📋 备份摘要已保存到: backup_summary.txt"
echo "📑 完整文件清单已保存到: backup_manifest.txt"
