---
title: las_video_edit API 速查
source: https://www.volcengine.com/docs/6492/2221469?lang=zh
---

# `las_video_edit`（视频智能剪辑）API 速查

本文件把文档中最关键的 **REST API 参数/返回字段**整理为可检索的“参考页”，用于在执行任务时快速对照。

## 基本信息

- **Base（区分 Region）**:
  - 北京：`https://operator.las.cn-beijing.volces.com/api/v1`
  - 上海：`https://operator.las.cn-shanghai.volces.com/api/v1`
  - Skill 里可用 `--region`（或 `LAS_REGION`/`REGION`/`region`）选择；也可用 `--api-base`（或 `LAS_API_BASE`）直接指定。
- **鉴权**: Header `Authorization: Bearer $LAS_API_KEY`
- **算子**:
  - `operator_id`: `las_video_edit`
  - `operator_version`: `v1`
- **异步模式**: `submit` 返回 `task_id`，用 `poll` 查询结果

## 1) submit：提交剪辑任务

- **URL**: `POST /submit`
- **用途**: 提交剪辑任务，对视频进行理解并输出“剪辑决策 + 片段文件（上传至 TOS）”。

### 请求体（JSON）

```json
{
  "operator_id": "las_video_edit",
  "operator_version": "v1",
  "data": {
    "video_url": "https://example.com/video.mp4",
    "task_name": "highlight_clip",
    "task_description": "提取戴帽子的小男孩的所有片段，包含台词",
    "reference_images": ["https://example.com/ref1.jpg", "tos://bucket/key/ref2.png"],
    "output_tos_path": "tos://bucket/path/to/output_dir",
    "segment_duration": 300,
    "mode": "normal",
    "min_segment_duration": 1,
    "output_format": "mp4"
  }
}
```

### `data` 字段说明

- `video_url`（string，必填）
  - 视频文件可下载地址。
  - 支持 `http/https`、以及火山 TOS `tos://bucket/key`。
- `output_tos_path`（string，必填）
  - 输出片段写入的 TOS 目录。
  - 片段通常以 `clip_001.mp4`, `clip_002.mp4`... 的形式写入该目录。
- `task_name`（string，可选）
  - 内置场景名（内置一段提示词）。
  - 与 `task_description` 二选一；**优先级高于 `task_description`**。
- `task_description`（string，可选）
  - 自然语言剪辑需求描述（建议写清“对象/动作/场景/是否需要台词”等）。
- `reference_images`（array，可选）
  - 参考图像列表（URL 或 TOS），用于辅助识别角色/物品/场景。
  - 推荐格式（按你提供的样例）：
    - `[{"target": "杜兰特", "images": ["https://...jpeg", "tos://bucket/key"]}]`
  - 说明：
    - `target`：要定位的目标名称（人/物/队伍等）
    - `images`：该目标的参考图列表（URL 或 TOS）
- `segment_duration`（integer，可选）
  - 子视频切分时长（秒）。
  - 文档提示不同模式支持的“最长视频”不同：简单/标准/精细模式上限逐级降低。
- `mode`（string，可选）
  - 处理模式，用于在速度/成本/质量间权衡。
  - 服务端校验的合法值：`simple`、`detail`。
  - 本 Skill 兼容常见别名：`normal`/`standard`/`fine`/`简单`/`标准`/`精细`。

## 脚本参数映射提示

- `--ref-target <name>` + 多个 `--ref-image <url_or_tos>` 会被组装为：
  - `reference_images = [{"target": <name>, "images": [..]}]`
- 或者用 `--ref-json/--ref-json-file` 直接提供 `reference_images` 的 JSON array（用于严格对齐服务端 schema）
- `min_segment_duration`（integer，可选，默认 `1`）
  - 短于该时长的片段会被过滤。
- `output_format`（string，可选）
  - 输出视频格式，示例支持 `mp4`、`mkv`。

### 返回体（submit）

submit 的核心是拿到 `metadata.task_id`：

- `metadata.task_id`（string）
- `metadata.task_status`（string）常见：`PENDING` / `RUNNING` / `COMPLETED` / `FAILED` / `TIMEOUT`
- `metadata.business_code`（string）业务码，成功通常为 `200`
- `metadata.error_msg`（string）失败时的错误信息

## 2) poll：查询任务状态与结果

- **URL**: `POST /poll`
- **用途**: 查询任务执行状态；若完成则返回剪辑片段列表。

### 请求体（JSON）

```json
{
  "operator_id": "las_video_edit",
  "operator_version": "v1",
  "task_id": "task-xxx"
}
```

### 返回体（poll）结构

顶层：

- `metadata`：任务元信息
  - `task_id`（string）
  - `task_status`（string）
    - `PENDING`：提交任务排队
    - `RUNNING`：运行中
    - `COMPLETED`：已完成
    - `FAILED`：失败
    - `TIMEOUT`：超时
  - `business_code`（string）
  - `error_msg`（string，可选）
- `data`：任务完成后的结构化输出（当 `task_status=COMPLETED` 时才有意义）

`data`（VideoEditResponse）常见字段：

- `total_segments`（integer）符合需求的片段总数
- `clips`（list of VideoClipInfo）剪辑后的视频片段列表
  - `clip_id`（string）如 `clip_001`
  - `start_time`（string）起始时间（`HH:MM:SS`）
  - `end_time`（string）结束时间（`HH:MM:SS`）
  - `duration`（float）片段时长（秒）
  - `description`（string）片段描述
  - `dialogue`（string，可选）片段对话（如适用，可能包含换行/台词）
  - `clip_url`（string）片段文件 URL（通常是 `tos://.../clip_001.mp4`）
  - `file_size`（integer）字节数
  - `confidence`（float）置信度（`0.0-1.0`）
  - `meta`（object）自定义元数据（用于承载你在 `task_description` 中要求提取的额外结构化信息）
- `video_duration`（float）原视频时长（秒）
- `resolution`（string）原视频分辨率（如 `1920x1080`）

## 常见要点（执行时的建议）

- `output_tos_path` 是强依赖：没有它通常无法产出 `clip_url`。
- 优先使用 `task_name`（如果你明确知道内置场景），否则用 `task_description`。
- `reference_images` 适合“找某个特定人/物”的需求，能显著提高定位准确度。
- `dialogue` 字段不保证一定存在：取决于视频是否有字幕/是否能抽取到对话。
