---
name: byted-las-vlm-video
description: |
  Video content understanding operator (las_vlm_video) via Doubao models.
  Use this skill when user needs to:
  - Analyze/describe video content with natural language prompts
  - Ask questions about what happens in a video (objects, actions, scenes)
  - Summarize video, extract key events, or generate captions
  Supports public/intranet-accessible video URLs and returns model responses + compression metadata.
  Requires LAS_API_KEY for authentication.
---

# LAS 视频内容理解（`las_vlm_video`）

本 Skill 用于调用 LAS `las_vlm_video` 算子进行视频理解（会先压缩视频到 50MB 以内，再调用豆包模型进行理解），并将同步 `process` 调用封装为可重复执行的脚本化工作流：

- `POST https://operator.las.cn-beijing.volces.com/api/v1/process` 同步处理

## 你需要准备什么

- `LAS_API_KEY`：优先从环境变量读取；也支持放在当前目录的 `env.sh`（内容形如 `export LAS_API_KEY="..."`）
- Operator Region（二选一）：
  - 环境变量：`LAS_REGION`（推荐）/ `REGION` / `region`，取值 `cn-beijing`（默认）或 `cn-shanghai`
  - 或在命令里通过 `--region cn-shanghai` 指定
- `video_url`：可下载的视频地址（`http/https` 或 `tos://bucket/key`）
- `prompt`：你希望模型对视频做什么理解/分析（例如“总结剧情”“列出关键事件”“回答我某个问题”）

## 参数与返回字段（详细版）

完整参数/返回字段速查见：

 - [references/api.md](references/api.md)

## 推荐使用方式

本 Skill 自带可执行脚本：`scripts/skill.py`。

为方便在不同工程/不同 Agent 之间迁移，下面示例默认你位于该 Skill 目录（与 `SKILL.md` 同级），因此命令使用相对路径 `scripts/skill.py`。

### 1) 执行视频理解

```bash
python3 scripts/skill.py process \
  --video-url "https://example.com/video.mp4" \
  --text "分析视频内容，输出要点列表，并回答：视频里出现了哪些主要物体？" \
  --model-name "doubao-seed-1.6-vision" \
  --region cn-beijing \
  --out result.json
```

### 2) 仅查看 endpoint 信息

```bash
python3 scripts/skill.py info --region cn-beijing
```

## Region / Endpoint 的选择逻辑

脚本解析顺序：

1) `--region` 命令行参数（`cn-beijing` 或 `cn-shanghai`）
2) 环境变量 `LAS_REGION` / `REGION` / `region`
3) 默认值 `cn-beijing`

Endpoint 由 region 自动映射到 `operator.las.<region>.volces.com`，不支持自定义 API base。

## 输出结果你会得到什么

当请求成功（`task_status=COMPLETED`）时，返回里通常会包含：

- `data.vlm_result`：豆包对话的原生返回（可直接取 `choices[0].message.content` 作为主要文本输出）
- `data.compress_result`：压缩前后的视频信息、压缩过程、耗时等元数据

脚本会把核心信息打印为易读摘要，并可选将原始 JSON 落盘。

## 常见问题

### 1) 提示“无法找到 LAS_API_KEY”怎么办？

- 优先推荐设置环境变量：`export LAS_API_KEY="..."`
- 或在运行目录准备 `env.sh`，内容形如：`export LAS_API_KEY="..."`
- 注意脚本是从“当前工作目录”读取 `env.sh`：如果你在别的目录运行，可能读不到。

### 2) 视频链接有什么限制？

- 视频需要公网或火山内网可访问（不可访问会导致失败）
- 视频文件占用存储空间需小于 1 GiB
- 算子暂不支持理解视频中的音频信息
