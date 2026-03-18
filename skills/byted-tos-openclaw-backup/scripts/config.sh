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

# 配置备份存储桶
# 用法: bash scripts/config.sh <存储桶名称>

set -euo pipefail

MOUNT_ROOT="/root/.openclaw/workspace"
CONFIG_FILE="$(dirname "$0")/../.config"

if [ $# -ne 1 ]; then
    echo "用法: bash scripts/config.sh <存储桶名称>"
    echo ""
    echo "可用存储桶:"
    df -P | grep "$MOUNT_ROOT" | awk '{print "  - " $NF}' | xargs basename
    exit 1
fi

TARGET_BUCKET="$1"

# 检查存储桶是否存在
MOUNT_POINT=$(df -P | grep "$MOUNT_ROOT" | awk '{print $NF}' | grep -E "/$TARGET_BUCKET$" | head -n 1)

if [ -z "$MOUNT_POINT" ]; then
    echo "❌ 存储桶 '$TARGET_BUCKET' 不存在或未挂载"
    echo "可用存储桶:"
    df -P | grep "$MOUNT_ROOT" | awk '{print "  - " $NF}' | xargs basename
    exit 1
fi

# 保存配置
echo "DEFAULT_BUCKET=\"$TARGET_BUCKET\"" > "$CONFIG_FILE"
echo "MOUNT_POINT=\"$MOUNT_POINT\"" >> "$CONFIG_FILE"

echo "✅ 备份存储桶已配置为: $TARGET_BUCKET"
echo "📂 挂载路径: $MOUNT_POINT"
echo "ℹ️  后续备份将自动使用此存储桶"
