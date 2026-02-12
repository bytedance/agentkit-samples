---
name: video-breakdown
description: 视频分镜拆解技能（自包含，无需外部后端）。使用 FFmpeg 预处理视频并生成分镜数据。(1) 视频 URL 直接处理 `python scripts/process_video.py "<video_url>"`；(2) 本地文件先上传 `python scripts/video_upload.py "<file_path>"` 获取 URL 后再处理。需要本机安装 FFmpeg。
---

# 视频分镜拆解 (Video Breakdown)

## 概述

视频分镜拆解技能通过本机 FFmpeg 将视频自动拆解为逐帧分镜，提供每个镜头的关键帧图片和时间信息。无需外部后端服务。

## 前置要求

- 本机安装 FFmpeg：`brew install ffmpeg`

## 使用步骤

### 方式一：视频 URL 直接处理

```bash
python scripts/process_video.py "https://example.com/video.mp4"
```

### 方式二：本地文件上传后处理

```bash
# 1. 上传本地视频到 TOS
python scripts/video_upload.py "/path/to/video.mp4"

# 2. 用返回的 video_url 处理
python scripts/process_video.py "<video_url>"
```

## 环境变量

| 变量名 | 必需 | 描述 |
|--------|------|------|
| `FFMPEG_BIN` | 否 | FFmpeg 路径，默认 `ffmpeg` |
| `FFPROBE_BIN` | 否 | FFprobe 路径，默认 `ffprobe` |
| `VOLCENGINE_ACCESS_KEY` | 上传时需要 | 火山引擎 Access Key |
| `VOLCENGINE_SECRET_KEY` | 上传时需要 | 火山引擎 Secret Key |
| `DATABASE_TOS_BUCKET` | 否 | TOS 存储桶名称 |
| `DATABASE_TOS_REGION` | 否 | TOS 区域，默认 `cn-beijing` |

## 输出格式

```json
{
  "task_id": "xxx",
  "duration": 30.5,
  "resolution": "1920x1080",
  "segment_count": 12,
  "segments": [
    {
      "index": 1,
      "start": 0.0,
      "end": 3.0,
      "frame_paths": ["path/to/frame.jpg"]
    }
  ]
}
```

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| FFmpeg not found | 安装 FFmpeg: `brew install ffmpeg` |
| 上传失败 | 检查 AK/SK 配置和 TOS 存储桶 |
| 视频下载失败 | 确认 URL 有效且可公开访问 |
