---
name: byted-las-video-resize
description: |
  Video resolution resize operator (las_video_resize).
  Use this skill when user needs to:
  - Resize video resolution into a target range (min/max width/height)
  - Preserve aspect ratio with increase/decrease/disable strategies
  - Control encoding quality options for GPU NVENC (cq/rc)
  Supports input from public URL/intranet URL/TOS and outputs to TOS. If user provides local video files or requires local outputs, use byted-tosfile-access to upload/download as a TOS bridge.
  Requires LAS_API_KEY for authentication.
---

# LAS 视频分辨率调整（`las_video_resize`）

本 Skill 基于以下两个接口，封装 `submit/poll` 异步调用流程：

- `POST https://operator.las.cn-beijing.volces.com/api/v1/submit` 提交任务
- `POST https://operator.las.cn-beijing.volces.com/api/v1/poll` 轮询任务状态并获取结果

## 你需要准备什么

- `LAS_API_KEY`：优先从环境变量读取；也支持放在当前目录的 `env.sh`（内容形如 `export LAS_API_KEY="..."`）
- Operator Region（二选一）：
  - 环境变量：`LAS_REGION`（推荐）/ `REGION` / `region`，取值 `cn-beijing`（默认）或 `cn-shanghai`
  - 或在命令里通过 `--region cn-shanghai` 指定
- `video_path`：输入视频的 TOS 路径或可下载的公网/内网 URL（`tos://bucket/key` 或 `http/https`）
- `output_tos_dir`：输出目录（`tos://bucket/prefix/`）
- `output_file_name`：输出文件名（如 `result.mp4`，同名会覆盖）
- 分辨率目标范围：`min_width/max_width/min_height/max_height`

## 参数与返回字段（详细版）

完整速查见：

- [references/api.md](references/api.md)

## 推荐使用方式

本 Skill 自带可执行脚本：`scripts/skill.py`。

下面示例默认你位于该 Skill 目录（与 `SKILL.md` 同级），因此命令使用相对路径 `scripts/skill.py`。

### 1) 仅提交（返回 task_id）

```bash
python3 scripts/skill.py submit \
  --video-path "tos://bucket/input.mp4" \
  --output-tos-dir "tos://bucket/output/" \
  --output-file-name "resized.mp4" \
  --min-width 1280 \
  --max-width 2560 \
  --min-height 720 \
  --max-height 1440 \
  --force-original-aspect-ratio-type increase \
  --force-divisible-by 2 \
  --region cn-beijing \
  --out submit.json
```

### 2) 查询任务状态（poll）

```bash
python3 scripts/skill.py poll task-xxx \
  --region cn-beijing \
  --out result.json
```

建议在对话中继续处理其他问题；每隔一段时间（例如 5-10 秒）再 poll 一次，直到 `task_status=COMPLETED` 后把 `data.output_path` 返回给用户。


## Region / Endpoint 的选择逻辑

脚本解析顺序：

1) `--region` 命令行参数（`cn-beijing` 或 `cn-shanghai`）
2) 环境变量 `LAS_REGION` / `REGION` / `region`
3) 默认值 `cn-beijing`

Endpoint 由 region 自动映射到 `operator.las.<region>.volces.com`，不支持自定义 API base。

## 输出结果你会得到什么

当任务 `COMPLETED` 时，返回里会包含：

- `data.output_path`：输出视频的 TOS 路径
- `data.width/height`：输出分辨率
- `data.duration`：视频时长

脚本会把核心信息打印为易读摘要，并可选将原始 JSON 落盘。

## 常见问题

### 1) 参数范围怎么设更合理？

- 如果你想要强制输出某个固定尺寸，可以将 `min_width=max_width` 且 `min_height=max_height`
- 若希望在不拉伸的情况下“尽量不小于目标尺寸”，用 `force_original_aspect_ratio_type=increase`（默认）
- 若希望在不拉伸的情况下“尽量不大于目标尺寸”，用 `force_original_aspect_ratio_type=decrease`

### 2) 覆盖同名输出文件是否危险？

是的，`output_tos_dir` 内若已有同名 `output_file_name` 会被覆盖。建议在文件名里带时间戳或业务标识。

## 补充：本地文件作为输入输出

`las_video_resize` 输入支持 TOS 或可下载 URL，输出必须写入 TOS。当用户给的是本地文件路径或希望本地落盘时，按下面规则处理，并配合 [byted-tosfile-access](../byted-tosfile-access/SKILL.md) 做上传/下载中转。

### 规则

- 用户输入是本地路径：先用 byted-tosfile-access 上传到 TOS，得到 `tos://...` 再调用本技能。
- 用户输出要求是本地路径：本技能先输出到 TOS（中转），再用 byted-tosfile-access 下载到用户指定本地路径。
- 用户输入与输出都要求本地：必须追问用户提供一个“可写的 TOS 中转目录前缀”（例如 `tos://bucket/tmp/video_resize/`），用它同时承载上传的输入与算子输出。
- 用户输入或输出有一项已经是 `tos://...` 且仍需要中转：优先复用该 bucket，并通过“路径改写”生成中转前缀，例如把 `tos://bucket/a/b/input.mp4` 改写成 `tos://bucket/a/b/video_resize/`（或 `tos://bucket/a/b/tmp/video_resize/`），避免覆盖原文件。

### 推荐编排（示例）

- 本地输入 → TOS 中转：上传本地视频到 `tos://bucket/tmp/video_resize/input.mp4`，然后把该 `tos://...` 作为 `--video-path`。
- TOS 输出 → 本地落盘：把 `--output-tos-dir` 指向 `tos://bucket/tmp/video_resize/`，待 `COMPLETED` 后拿 `data.output_path` 再下载到本地。
