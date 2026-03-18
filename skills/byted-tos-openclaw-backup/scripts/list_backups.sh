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

# 列出所有备份记录

set -e

WORKSPACE_DIR="/root/.openclaw/workspace"
BACKUP_ROOT="openclaw_backup"

# 检测挂载的网盘
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
fi

BACKUP_BASE="$MOUNT_POINT/$BACKUP_ROOT"

if [ ! -d "$BACKUP_BASE" ]; then
    echo "ℹ️  暂无备份记录"
    exit 0
fi

echo "📋 现有备份列表 (存储桶: $BUCKET_NAME):"
echo "====================================="

for backup_dir in "$BACKUP_BASE"/*/; do
    if [ -d "$backup_dir" ]; then
        date_name=$(basename "$backup_dir")
        if [ -f "$backup_dir/backup_summary.txt" ]; then
            file_count=$(grep "备份文件数" "$backup_dir/backup_summary.txt" | awk '{print $4}')
            size=$(grep "总大小" "$backup_dir/backup_summary.txt" | awk '{print $4}')
            echo "📅 $date_name ($file_count files, $size)"
        else
            file_count=$(find "$backup_dir" -type f | wc -l)
            size=$(du -sh "$backup_dir" | cut -f1)
            echo "📅 $date_name ($file_count files, $size)"
        fi
    fi
done
