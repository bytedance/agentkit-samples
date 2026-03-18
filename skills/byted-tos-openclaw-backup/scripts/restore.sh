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

# 恢复备份脚本
# 用法: bash scripts/restore.sh <备份日期> [--dry-run]

set -euo pipefail

MOUNT_ROOT="/root/.openclaw/workspace"
BACKUP_ROOT="openclaw_backup"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../.config"
DRY_RUN=false

if [ $# -lt 1 ]; then
    echo "用法: bash scripts/restore.sh <备份日期> [--dry-run]"
    echo ""
    echo "示例:"
    echo "  bash scripts/restore.sh 2026-03-11          # 恢复2026-03-11的备份"
    echo "  bash scripts/restore.sh 2026-03-11 --dry-run # 预览恢复操作，不实际执行"
    echo ""
    echo "可用备份:"
    bash "$SCRIPT_DIR/list_backups.sh"
    exit 1
fi

BACKUP_DATE="$1"
if [ $# -eq 2 ] && [ "$2" = "--dry-run" ]; then
    DRY_RUN=true
    echo "🔍 预览模式：不会实际修改文件"
fi

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
fi

BACKUP_DIR="$MOUNT_POINT/$BACKUP_ROOT/$BACKUP_DATE"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ 备份 $BACKUP_DATE 不存在"
    echo "可用备份:"
    bash "$SCRIPT_DIR/list_backups.sh"
    exit 1
fi

echo "📂 准备恢复备份: $BACKUP_DATE"
echo "📦 存储桶: $BUCKET_NAME"
echo "📂 备份路径: $BACKUP_DIR"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "🔍 预览恢复操作:"
    echo "  - 恢复核心配置文件到: /root/.openclaw/workspace/"
    echo "  - 恢复系统配置到: /root/.openclaw/"
    echo "  - 恢复技能文件到: /root/.openclaw/extensions/ 和 /root/.openclaw/workspace/skills/"
    echo "  - 恢复记忆数据到: /root/.openclaw/workspace/memory/"
    echo ""
    echo "📋 备份内容摘要:"
    cat "$BACKUP_DIR/backup_summary.txt" 2>/dev/null || echo "  无摘要信息"
    exit 0
fi

read -p "⚠️  恢复操作会覆盖现有文件，确定要继续吗? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 已取消恢复"
    exit 1
fi

echo ""
echo "🔄 开始恢复..."

# 恢复核心配置文件
echo "📝 恢复核心配置文件..."
cp "$BACKUP_DIR"/*.md /root/.openclaw/workspace/ 2>/dev/null || echo "ℹ️  无核心配置文件需要恢复"

# 恢复系统配置
echo "⚙️  恢复系统配置..."
if [ -d "$BACKUP_DIR/config" ]; then
    cp -r "$BACKUP_DIR/config"/* /root/.openclaw/ 2>/dev/null
    echo "✅ 系统配置恢复完成"
else
    echo "ℹ️  无系统配置需要恢复"
fi

# 恢复技能文件
echo "🔧 恢复技能文件..."
if [ -d "$BACKUP_DIR/skills/extensions" ]; then
    cp -r "$BACKUP_DIR/skills/extensions/"* /root/.openclaw/extensions/ 2>/dev/null
fi
if [ -d "$BACKUP_DIR/skills/workspace" ]; then
    cp -r "$BACKUP_DIR/skills/workspace/"* /root/.openclaw/workspace/skills/ 2>/dev/null
fi
echo "✅ 技能文件恢复完成"

# 恢复记忆数据
echo "🧠 恢复记忆数据..."
if [ -d "$BACKUP_DIR/memory" ]; then
    mkdir -p /root/.openclaw/workspace/memory
    cp -r "$BACKUP_DIR/memory"/* /root/.openclaw/workspace/memory/ 2>/dev/null
    echo "✅ 记忆数据恢复完成"
else
    echo "ℹ️  无记忆数据需要恢复"
fi

echo ""
echo "✅ 恢复完成！"
echo "📅 恢复的备份日期: $BACKUP_DATE"
echo "⚠️  建议重启OpenClaw服务以应用所有配置"
