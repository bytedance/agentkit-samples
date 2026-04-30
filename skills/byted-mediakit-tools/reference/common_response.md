# 统一返回格式

除 `understand_video_content`（视频理解）外，异步能力的 HTTP 结果与 CLI 包装的 `status` / `task_id` 等字段约定如下。

## 视频理解（同步，直接返回模型结果）

```json
{
  "status": "success",
  "result": {
    "choices": [
      {
        "role": "assistant",
        "content": "视频内容分析结果..."
      }
    ]
  }
}
```

## 异步能力 — 成功（默认自动等待结果）

```json
{
  "task_id": "amk-tool-extract-audio-xxxxxxxxxxxxxx",
  "duration": 82.454056,
  "play_url": "https://example.vod.cn-north-1.volcvideo.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.mp3?preview=1&auth_key=***",
  "request_id": "20260401xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "status": "completed",
  "task_type": "extract-audio"
}
```

## 异步能力 — `--no-wait`（仅返回 task_id）

```json
{
  "status": "pending",
  "task_id": "amk-xxx-xxx",
  "message": "任务已提交，已跳过等待，可调用 query_task 接口传入 task_id 查询结果",
  "query_example": "./byted-mediakit-tools.sh query_task --task_id amk-xxx-xxx"
}
```

## 错误 / 超时

```json
{
  "status": "failed/canceled/timeout",
  "task_id": "amk-xxx-xxx",
  "message": "错误详情"
}
```
