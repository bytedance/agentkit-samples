---
name: byted-las-audio-convert
description: |
  Audio format conversion operator.
  Use this skill when user needs to:
  - Convert audio files between formats (wav, mp3, flac)
  - Change audio properties (sample rate, bit rate) using ffmpeg params
  Supports input from TOS and output to TOS.
  Requires LAS_API_KEY for authentication.
---

# LAS-AUDIO-CONVERT (las_audio_convert)

本 Skill 用于调用 LAS 音频转换算子，支持将 TOS 上的音频文件转换为指定格式并存储回 TOS。

- `POST https://operator.las.cn-beijing.volces.com/api/v1/process` 同步处理

## 快速开始

在本 skill 目录执行：

```bash
python3 scripts/skill.py --help
```

### 执行音频转换

```bash
python3 scripts/skill.py process \
  --input-path "tos://bucket/input.mp3" \
  --output-path "tos://bucket/output.wav" \
  --output-format wav
```

## 参数说明

- `input_path`: 输入文件的 TOS 路径。
- `output_path`: 输出文件的 TOS 路径。
- `output_format`: 目标格式，支持 wav, mp3, flac，默认 wav。
- `extra_params`: 额外的 ffmpeg 参数，如 `["-ar", "44100"]`。

## 常见问题

- 确保 TOS 路径有读写权限。
- API Key 需通过环境变量 `LAS_API_KEY` 或 `env.sh` 配置。
