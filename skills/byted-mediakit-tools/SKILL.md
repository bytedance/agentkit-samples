---
name: byted-mediakit-tools
description: 火山引擎 AI MediaKit 音视频处理工具集，提供视频理解、音频提取、视频剪辑、音视频拼接、画质增强、文生视频、音视频合成，以及本地翻转、调速、字幕、水印、转码等能力。当用户提及音频剪辑、视频剪辑、音视频拼接、文生视频、音频提取、画质增强、视频理解、音视频合成、媒体裁剪、视频翻转、调速、加字幕、加水印、转码等需求时必须调用本Skill。当用户需要视频理解时，宿主agent必须自动解析用户的具体要求作为prompt参数传入，同时传入视频URL和fps参数；max_frames 为可选参数。
version: 1.0.0
license: Apache-2.0
metadata:
  display_name: 火山引擎音视频处理工具集
  version: 1.0.0
  permissions:
    - network
    - file_read
    - file_write
    - temp_storage
  env:
    - name: AMK_API_KEY
      description: AMK（AI MediaKit）访问密钥；配置完整时使用云端剪辑/拼接/提取/合成能力，缺失时这些能力自动回退到本地 FFmpeg
      required: false
      secret: true
      default: ''
    - name: AMK_ENV
      description: AMK 服务端环境，仅支持 prod（生产）
      required: false
      secret: false
      default: 'prod'
    - name: AMK_ENABLE_CLIENT_TOKEN
      description: 为 true 时，除视频理解外的请求会自动携带 8 位 client_token（幂等）；取值 true / false
      required: false
      secret: false
      default: 'false'
    - name: ARK_API_KEY
      description: 火山引擎方舟 OpenAPI 密钥，仅在使用视频理解（understand_video_content）时需要
      required: false
      secret: true
      default: ''
    - name: ARK_MODEL_ID
      description: 方舟模型 ID，仅在使用视频理解（understand_video_content）时需要
      required: false
      secret: false
      default: ''
---

> **说明**：宿主若在环境中注入 `ARK_SKILL_API_BASE` / `ARK_SKILL_API_KEY`（例如供其他 Skill 走 SkillHub 网关），与本 Skill 的 `AMK_API_KEY`、`ARK_API_KEY`（视频理解）**相互独立**，请勿混淆。

> ⚠️ **严格执行**：音视频裁剪、拼接、音频提取、音视频合成会自动选择执行后端：云端环境完整且输入为 URL 时走 AMK 云端；云端必需配置/依赖缺失，或输入是本地文件路径时，自动走本地 FFmpeg。视频翻转、调速、加字幕、加水印、转码是本地原生命令，始终走本地 FFmpeg。不要为了这些本地能力向用户索取云端环境变量。

> `<SKILL_DIR>` 为 `byted-mediakit-tools` 所在目录。
> 当前方法返回的 `链接仅供下载，不支持播放能力`
> `禁止修改任何返回数据信息`，如 `play_url` 、`request_id` 、`task_id` 等
> 用户明确声明需要重新执行时：除 `understand_video_content` 外的方法需 **生成新的 `client_token`（不要复用上一次的 `client_token`）**，避免命中上次的幂等结果

# 火山引擎 AI MediaKit 音视频处理工具集

## 概览

本工具集支持以下音视频处理能力。标记为“云端&本地”的能力会自动选择执行后端：云端配置完整且输入为 URL 时走 AMK 云端；云端不可用或输入为本地路径时走本地 FFmpeg。

| 能力 | 支持范围 | 说明 |
| --- | --- | --- |
| 视频理解 | 云端 | AI 分析视频内容，生成自然语言描述 |
| 音视频裁剪 | 云端&本地 | 精确裁剪音频或视频时长 |
| 音视频拼接 | 云端&本地 | 拼接多个音频或视频片段；云端支持转场 ID，本地支持 FFmpeg 转场名 |
| 音频提取 | 云端&本地 | 从视频中提取音频轨道 |
| 音视频合成 | 云端&本地 | 合成或替换视频音轨；云端支持时长对齐策略，本地支持混音/替换 |
| 画质增强 | 云端 | 提升视频画质、分辨率、帧率 |
| 文生视频 | 云端 | 图片生成视频，支持动画和转场 |
| 视频翻转 | 本地 | 水平、垂直或双向翻转 |
| 视频调速 | 本地 | 调整视频与音频播放速度 |
| 视频加字幕 | 本地 | 添加 SRT/ASS 硬字幕|
| 视频加水印 | 本地 | 添加图片/水印，支持位置、缩放和显示时间 |
| 视频转码/转封装 | 本地 | 转换封装格式或重编码 |

---

## 获取密钥

如需使用云端能力，请先获取 API 密钥；本地可覆盖能力在密钥缺失时会自动使用 FFmpeg：

- **AI MediaKit 控制台**：https://console.volcengine.com/imp/ai-mediakit/
- **方舟模型与密钥**：https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seed-1-8

---

## 快速开始

### 1. 环境配置

在 `<SKILL_DIR>/.env` 中配置环境变量（首次使用会自动创建模板）：

```bash
# AMK API Key（云端能力需要；本地回退不需要）
AMK_API_KEY=your_amk_api_key_here
# AMK 环境固定为 prod
AMK_ENV=prod
# 是否启用 client_token 自动注入（用于幂等）
AMK_ENABLE_CLIENT_TOKEN=false
# 方舟 密钥（可选，仅使用视频理解功能时必须配置）
ARK_API_KEY=your_ark_api_key_here
# 方舟 模型ID（可选，仅使用视频理解功能时必须配置）
ARK_MODEL_ID=doubao-seed-1-8
```

### 2. 依赖安装

```bash
cd <SKILL_DIR>/scripts
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

---

## 核心功能

### 同步能力（立即返回结果）

| 能力                         | 说明                                             |
| ---------------------------- | ------------------------------------------------ |
| **understand_video_content** | 视频内容理解，使用 AI 分析视频并生成自然语言描述 |

### 异步能力（默认自动等待结果）

| 能力                      | 说明                                    |
| ------------------------- | --------------------------------------- |
| **trim_media_duration**   | 裁剪音视频时长，精确到毫秒              |
| **concat_media_segments** | 拼接多个音视频片段，支持转场效果        |
| **extract_audio**         | 从视频中提取音频轨道，支持 mp3/m4a 格式 |
| **enhance_video**         | 视频画质增强，支持超分、插帧等          |
| **image_to_video**        | 图片生成视频，支持动画和转场            |
| **mux_audio_video**       | 音视频合成，支持时长对齐                |

### 辅助能力

| 能力           | 说明                       |
| -------------- | -------------------------- |
| **query_task** | 查询异步任务执行状态和结果 |

### 本地原生命令

| 能力 | 说明 |
| --- | --- |
| **flip-video** / **flip_video** | 视频翻转，默认水平镜像 |
| **adjust-speed** / **adjust_speed** | 视频调速 |
| **add-subtitle** / **add_subtitle** | 视频加硬字幕，支持 SRT/ASS |
| **add-overlay** / **add_overlay** | 视频加图片/水印 |
| **transcode** | 视频转码/转封装 |

---

## 使用示例

### 视频理解

```bash
./byted-mediakit-tools.sh understand_video_content \
  --video_url "https://example.com/video.mp4" \
  --prompt "总结视频内容" \
  --fps 1
```

### 视频裁剪

```bash
# 云端：输入为 URL 且 AMK 配置完整
./byted-mediakit-tools.sh trim_media_duration \
  --type video \
  --source "https://example.com/video.mp4" \
  --start_time 0 \
  --end_time 10

# 本地回退：输入为本地文件，或 AMK 配置不完整
./byted-mediakit-tools.sh trim_media_duration \
  --type video \
  --source "/path/to/input.mp4" \
  --start_time 0 \
  --end_time 10 \
  --output "/path/to/output.mp4"
```

### 音视频拼接

```bash
./byted-mediakit-tools.sh concat_media_segments \
  --type video \
  --sources "https://example.com/1.mp4" "https://example.com/2.mp4"
```

### 音频提取

```bash
./byted-mediakit-tools.sh extract_audio \
  --video_url "https://example.com/video.mp4" \
  --format mp3
```

### 画质增强

```bash
./byted-mediakit-tools.sh enhance_video \
  --video_url "https://example.com/video.mp4" \
  --tool_version professional \
  --resolution 1080p
```

### 图片生成视频

```bash
./byted-mediakit-tools.sh image_to_video \
  --images "image_url=https://example.com/1.jpg,duration=3,animation_type=zoom_in" \
           "image_url=https://example.com/2.jpg,duration=3,animation_type=pan_left"
```

### 音视频合成

```bash
./byted-mediakit-tools.sh mux_audio_video \
  --video_url "https://example.com/video.mp4" \
  --audio_url "https://example.com/audio.mp3" \
  --is_audio_reserve false
```

### 本地翻转 / 调速 / 字幕 / 水印 / 转码

```bash
./byted-mediakit-tools.sh flip-video -i input.mp4 --direction horizontal -o flipped.mp4
./byted-mediakit-tools.sh adjust-speed -i input.mp4 --speed 2.0 -o speed.mp4
./byted-mediakit-tools.sh add-subtitle -i input.mp4 --subtitle sub.srt -o subtitled.mp4
./byted-mediakit-tools.sh add-overlay -i input.mp4 --image logo.png --position top-right -o watermarked.mp4
./byted-mediakit-tools.sh transcode -i input.mov --format mp4 --codec h264 -o output.mp4
```

### 异步任务（不等待结果）

```bash
# 使用 --no-wait 立即返回 task_id
./byted-mediakit-tools.sh --no-wait trim_media_duration \
  --type video \
  --source "https://example.com/video.mp4" \
  --start_time 0 \
  --end_time 10

# 查询任务结果
./byted-mediakit-tools.sh query_task --task_id "amk-xxx-xxx"
```

---

## 响应格式

### 同步响应（视频理解）

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

### 异步响应（默认自动等待）

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

### 异步响应（--no-wait）

```json
{
  "status": "pending",
  "task_id": "amk-xxx-xxx",
  "message": "任务已提交，已跳过等待，可调用 query_task 接口传入 task_id 查询结果",
  "query_example": "./byted-mediakit-tools.sh query_task --task_id amk-xxx-xxx"
}
```

### 错误响应

```json
{
  "status": "failed/canceled/timeout",
  "task_id": "amk-xxx-xxx",
  "message": "错误详情"
}
```

---

## 详细文档

各功能的详细参数说明请参考 `reference/` 目录下的对应文档：

| 能力                     | 文档链接                                                                       |
| ------------------------ | ------------------------------------------------------------------------------ |
| understand_video_content | [reference/understand_video_content.md](reference/understand_video_content.md) |
| query_task               | [reference/query_task.md](reference/query_task.md)                             |
| concat_media_segments    | [reference/concat_media_segments.md](reference/concat_media_segments.md)       |
| enhance_video            | [reference/enhance_video.md](reference/enhance_video.md)                       |
| extract_audio            | [reference/extract_audio.md](reference/extract_audio.md)                       |
| image_to_video           | [reference/image_to_video.md](reference/image_to_video.md)                     |
| mux_audio_video          | [reference/mux_audio_video.md](reference/mux_audio_video.md)                   |
| trim_media_duration      | [reference/trim_media_duration.md](reference/trim_media_duration.md)           |
| 统一响应格式             | [reference/common_response.md](reference/common_response.md)                   |
| 本地回退策略             | [reference/local_fallback.md](reference/local_fallback.md)                     |

---

## 注意事项

1. **返回链接**：所有返回的 `play_url` 等链接仅供下载，不支持直接播放
2. **幂等性**：重新执行任务时，请确保生成新的 `client_token`（`AMK_ENABLE_CLIENT_TOKEN=true` 时自动处理）
3. **视频理解**：使用视频理解功能必须配置 `ARK_API_KEY` 和 `ARK_MODEL_ID`
4. **超时处理**：大文件处理可能耗时较长，建议使用 `--no-wait` 配合 `query_task` 轮询
5. **本地能力**：`trim_media_duration`、`concat_media_segments`、`extract_audio`、`mux_audio_video` 支持本地 FFmpeg 回退；`flip-video`、`adjust-speed`、`add-subtitle`、`add-overlay`、`transcode` 始终走本地 FFmpeg；`enhance_video`、`image_to_video`、`understand_video_content`、`query_task` 仅走云端

---

© 北京火山引擎科技有限公司 2026 版权所有
