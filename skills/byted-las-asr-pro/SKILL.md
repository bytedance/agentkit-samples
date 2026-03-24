---
name: byted-las-asr-pro
description: |
  ASR (Automatic Speech Recognition) — enhanced speech-to-text built on Doubao large model, with audio preprocessing, denoising, and extended analysis capabilities. Async API.
  Choose this skill when:
  - Input is a video file (mp4/mov/mkv) — auto-extracts audio track
  - Audio needs denoising before recognition
  - File exceeds 512MB or 5 hours (no size limit)
  - Audio source is a TOS internal path (tos://bucket/key)
  - Need structured JSON output with timestamped utterances and metadata
  - Need speaker diarization, emotion/gender detection, speech rate, or sensitive word filtering
  Supports 99 languages, multiple formats (wav/mp3/m4a/aac/flac/ogg/mp4/mov/mkv), and auto language detection.
---

# LAS-ASR-PRO（las_asr_pro）

本 Skill 用于把「LAS-ASR-PRO 接口文档」里的 `submit/poll` 异步调用流程，封装成可重复使用的脚本化工作流：

- `POST https://operator.las.cn-beijing.volces.com/api/v1/submit` 提交转写任务
- `POST https://operator.las.cn-beijing.volces.com/api/v1/poll` 轮询任务状态并获取识别结果

## 快速开始

在本 skill 目录执行：

```bash
python3 scripts/skill.py --help
```

### 提交并等待

```bash
python3 scripts/skill.py submit \
  --audio-url "https://example.com/audio.wav" \
  --audio-format wav \
  --model-name bigmodel \
  --region cn-beijing \
  --out result.json
```

### 仅提交（返回 task_id）

```bash
python3 scripts/skill.py submit \
  --audio-url "https://example.com/audio.wav" \
  --audio-format wav \
  --no-wait
```

### 轮询 / 等待

```bash
python3 scripts/skill.py poll <task_id>
python3 scripts/skill.py wait <task_id> --timeout 1800 --out result.json
```

## 参数与返回字段

详见 `references/api.md`。

## 常见问题

- API Key 未找到：设置环境变量 `LAS_API_KEY` 或提供 `env.sh`。
- Parameter.Invalid：检查字段结构/枚举值是否符合文档（推荐先最小化 payload，再逐项加字段）。
- `audio_format` 不正确：请确保容器格式与真实音频一致（以服务端支持为准）。
