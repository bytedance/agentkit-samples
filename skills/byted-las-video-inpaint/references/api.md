---
title: las_video_inpaint API 参考
---

# `las_video_inpaint` API 参考

`las_video_inpaint` 为异步算子：先 `submit` 获取 `task_id`，再 `poll` 轮询直到 `COMPLETED/FAILED`。

## Base / Region

- Submit: `POST https://operator.las.<region>.volces.com/api/v1/submit`
- Poll: `POST https://operator.las.<region>.volces.com/api/v1/poll`
- Region:
  - `cn-beijing` → `operator.las.cn-beijing.volces.com`
  - `cn-shanghai` → `operator.las.cn-shanghai.volces.com`
- 鉴权：`Authorization: Bearer $LAS_API_KEY`

## Submit 请求体

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_video_inpaint` |
| operator_version | string | 是 | 固定为 `v1` |
| data | VideoInpaintUserReqParams | 是 | 参数详情见下 |

### VideoInpaintUserReqParams

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| video_url | string | 是 | 视频下载地址（http/https 或 tos://） |
| output_tos_path | string | 是 | 修复结果写入的 TOS 路径前缀（建议传目录前缀）。最终输出以 `inpainted_video_path` 为准 |
| targets | array<string> | 否 | `watermark/subtitle/scrolling_subtitle`，默认 `["watermark","subtitle"]` |
| return_subtitle_bbox | boolean | 否 | 是否返回字幕 bbox，默认 true |
| detection_precise_mode | boolean | 否 | 是否启用精确检测模式 |
| inpainting_backend | string | 否 | `pixel_replace/pixel_generate`，默认 `pixel_replace` |
| max_process_frames | integer | 否 | 最大处理帧数，`-1` 表示不限制 |
| subtitle_mask_precise | boolean | 否 | 是否启用精确字幕遮罩 |
| fixed_bboxes | array<array<int>> | 否 | 固定修复区域：`[x1,y1,x2,y2]`，以 1000x1000 为基准 |

## Poll 请求体

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_video_inpaint` |
| operator_version | string | 是 | 固定为 `v1` |
| task_id | string | 是 | submit 返回的任务 ID |

## Poll 响应体（摘要）

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| metadata.task_status | string | `PENDING/RUNNING/COMPLETED/FAILED/TIMEOUT` |
| data.inpainted_video_path | string | 修复后视频的 TOS 地址 |
| data.subtitle_bbox | string | 字幕 bbox（如果返回），格式 `x1,y1,x2,y2` |
