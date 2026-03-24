---
name: byted-las-video-inpaint
description: |
  Video inpainting operator (las_video_inpaint) for removing watermarks/subtitles/logos from videos.
  Use this skill when user needs to:
  - Remove watermarks, subtitles, or scrolling subtitles from a video
  - Repair a video by inpainting fixed regions (fixed_bboxes) or auto-detected regions
  - Run video restoration and get the output TOS path + optional subtitle bbox
  Supports input from public URL/intranet URL/TOS and outputs to TOS. If user provides local video files or requires local outputs, use byted-tosfile-access to upload/download as a TOS bridge.
  Requires LAS_API_KEY for authentication.
---

# LAS 视频修复（`las_video_inpaint`）

本 Skill 基于以下两个接口，封装 `submit/poll` 异步调用流程。

- `POST https://operator.las.cn-beijing.volces.com/api/v1/submit` 提交修复任务
- `POST https://operator.las.cn-beijing.volces.com/api/v1/poll` 轮询任务状态并拿到修复后视频

## 你需要准备什么

- `LAS_API_KEY`：优先从环境变量读取；也支持放在当前目录的 `env.sh`
- Operator Region（二选一）：
  - 环境变量：`LAS_REGION`（推荐）/ `REGION` / `region`，取值 `cn-beijing`（默认）或 `cn-shanghai`
  - 或命令中通过 `--region cn-shanghai` 指定
- `video_url`：可下载的视频地址（`http/https` 或 `tos://bucket/key`）
- `output_tos_path`：修复结果写入的 TOS 路径前缀（建议传目录前缀）。实际输出以 `inpainted_video_path` 为准

## 参数与返回字段（详细版）

完整速查见：

- [references/api.md](references/api.md)

## 推荐使用方式

本 Skill 自带可执行脚本：`scripts/skill.py`。

下面示例默认你位于该 Skill 目录（与 `SKILL.md` 同级），因此命令使用相对路径 `scripts/skill.py`。

### 1) 仅提交（返回 task_id）

```bash
python3 scripts/skill.py submit \
  --video-url "tos://bucket/input.mp4" \
  --output-tos-path "tos://bucket/output/" \
  --targets watermark \
  --targets subtitle \
  --region cn-beijing \
  --out submit.json
```

### 2) 查询任务状态（poll）

```bash
python3 scripts/skill.py poll task-xxx \
  --region cn-beijing \
  --out result.json
```

建议在对话中继续处理其他问题；每隔一段时间（例如 5-10 秒）再 poll 一次，直到 `task_status=COMPLETED` 后把 `data.inpainted_video_path` 返回给用户。


## 关键参数说明

- `targets`：擦除目标类型，常用 `watermark/subtitle/scrolling_subtitle`，默认服务端通常为 `["watermark","subtitle"]`
- `fixed_bboxes`：如果你只想修复某些固定区域，可用该参数。坐标以 `1000x1000` 为基准，会按实际分辨率缩放
- `return_subtitle_bbox`：是否返回字幕 bbox（字符串 `x1,y1,x2,y2`，原视频像素坐标）
- 如果你传入的是带 `.mp4` 的路径（看起来像文件），服务端可能仍会在该路径下追加任务目录与文件名；建议使用目录前缀，避免出现 `...mp4/<task_dir>/<file>.mp4` 的层级

## 使用限制（摘要）

- 视频源需可访问（公网/火山内网/TOS）
- 视频时长 ≤ 4 小时，大小 ≤ 30GB

## 补充：本地文件作为输入输出

`las_video_inpaint` 输入支持TOS或可下载URL，输出必须写入 TOS 上（最终以 `inpainted_video_path` 为准）。当用户给的是本地文件路径或希望本地落盘时，按下面规则处理，并配合 [byted-tosfile-access](../byted-tosfile-access/SKILL.md) 做上传/下载中转。

### 规则

- 用户输入是本地路径：先用 byted-tosfile-access 上传到 TOS，得到 `tos://...` 再作为 `--video-url` 调用本技能。
- 用户输出要求是本地路径：本技能先输出到 TOS（中转），待 `COMPLETED` 后用 byted-tosfile-access 把 `inpainted_video_path` 下载到本地。
- 用户输入与输出都要求本地：必须追问用户提供一个“可写的 TOS 中转目录前缀”（例如 `tos://bucket/tmp/video_inpaint/`），用它同时承载上传的输入与算子输出。
- 用户输入或输出有一项已经是 `tos://...` 且仍需要中转：优先复用该 bucket，并通过“路径改写”生成中转前缀，例如把 `tos://bucket/a/b/input.mp4` 改写成 `tos://bucket/a/b/video_inpaint/`（或 `tos://bucket/a/b/tmp/video_inpaint/`），避免覆盖原文件。
