---
name: byted-las-audio-extract-and-split
description: |
  Audio extract and split operator.
  Use this skill when user needs to:
  - Extract audio from video files (mp4, wmv, etc.)
  - Split audio into segments of specific duration
  - Convert audio format (wav, mp3, flac)
  Supports input from TOS and output to TOS.
  Requires LAS_API_KEY for authentication.
---

# LAS-AUDIO-EXTRACT-AND-SPLIT (las_audio_extract_and_split)

本 Skill 用于调用 LAS 音频切分算子，支持从视频/音频中提取音频并按时长切分。

- `POST https://operator.las.cn-beijing.volces.com/api/v1/process` 同步处理

## 快速开始

在本 skill 目录执行：

```bash
python3 scripts/skill.py --help
```

### 执行音频切分

```bash
python3 scripts/skill.py process \
  --input-path "tos://bucket/input.mp4" \
  --output-path-template "tos://bucket/output/{index}.wav" \
  --split-duration 30 \
  --output-format wav
```

## 参数说明

- `input_path`: 输入文件的 TOS 路径。
- `output_path_template`: 输出文件路径模版。支持变量 `{index}`, `{index1}`, `{ordinal}`, `{hours}`, `{duration}`, `{output_file_ext}`。
- `split_duration`: 切片时长（秒），默认 30。
- `output_format`: 输出格式，支持 wav, mp3, flac，默认 wav。

## 常见问题

- 确保 TOS 路径有读写权限。
- API Key 需通过环境变量 `LAS_API_KEY` 或 `env.sh` 配置。
