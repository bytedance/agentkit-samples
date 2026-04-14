---
title: las_long_video_understand API 参考
---

# `las_long_video_understand` API 参考

`las_long_video_understand` 为异步算子：先 `submit` 获取 `task_id`，再 `poll` 轮询直到 `COMPLETED/FAILED`。

## Base / Region

- API Base: `https://operator.las.<region>.volces.com/api/v1`
- Region:
  - `cn-beijing`
  - `cn-shanghai`

鉴权：`Authorization: Bearer $LAS_API_KEY`

## Submit 请求体

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_long_video_understand`（CLI 自动填充） |
| operator_version | string | 是 | 固定为 `v1`（CLI 自动填充） |
| data | long_video_understand | 是 | **`data.json` 的内容对应此字段**，详情见下表 |

### data 参数 (long_video_understand)

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| video_url | string | 是 | 视频 URL（http/https 或 tos://） |
| query | string | 否 | 视频理解的查询，例如 "请总结这个视频的主要内容" |
| fps | float | 否 | 抽帧率 |
| media_resolution | string | 否 | 媒体分辨率 |
| model_name | string | 否 | 默认使用的模型名称，如 "doubao-seed-2-0-lite-260215" |
| reasoning_effort | string | 否 | 推理消耗程度 |
| clip_context | string | 否 | 片段上下文 |

## Poll 响应结构 (data 对象)

`COMPLETED` 状态下，`data` 包含以下核心字段：

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| final_summary | string | 视频的最终总结 |
| video_duration | float | 视频总时长 |
| resolution | string | 视频分辨率 |
| total_clips | int | 总片段数 |
| clips | list | 包含每个视频片段的详情，如 `clip_id`, `start_time`, `end_time`, `duration`, `answer` 等 |
| token_usages | list | 各模型的 token 消耗统计 |
