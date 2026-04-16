#!/bin/bash
TASK_ID="$1"
VIDEO_FILE="$2"
SESSION="$3"
CHANNEL="$4"
ACCOUNT="$5"

# 确保输出目录存在
mkdir -p "$(dirname "$VIDEO_FILE")"
# 记录开始时间和超时时间（1小时=3600秒）
START_TIME=$(date +%s)
TIMEOUT_SECONDS=3600

while true; do
    # 检查是否超时
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    if [ "$ELAPSED" -ge "$TIMEOUT_SECONDS" ]; then
        echo timeout
        exit 1
    fi

    # 调用task.py查询，忽略错误输出
    RESULT=$(python3 task.py --id "$TASK_ID" --output "$VIDEO_FILE" 2>/dev/null)
    # 检查是否存在code字段
    CODE=$(echo "$RESULT" | jq -r '.code' 2>/dev/null || echo '-1')
    
    if [ "$CODE" = "0" ]; then
        # 任务成功：输出结果文件内容
        openclaw agent --session-id "$SESSION" -m "任务 $TASK_ID 执行成功，任务结果见$RESULT。阅读「消费成片指南.md」中「八、任务结果处理」章节，将任务结果告知用户。" --deliver --reply-channel "$CHANNEL" --reply-to "$ACCOUNT"
        exit 0
    elif [ "$CODE" = "1000" ] || [ "$CODE" = "-1" ]; then
        # 任务执行中/查询失败：等待30秒后重试
        sleep 30
        continue
    else
        # 任务失败：输出错误信息
        openclaw agent --session-id "$SESSION" -m "任务 $TASK_ID 执行失败，失败原因见$RESULT。阅读「消费成片指南.md」中「八、任务结果处理」章节，将任务结果告知用户。" --deliver --reply-channel "$CHANNEL" --reply-to "$ACCOUNT"
        exit 1
    fi
done