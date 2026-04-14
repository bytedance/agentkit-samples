---
title: las_video_resize API 参考
---

# `las_video_resize` API 参考

`las_video_resize` 为异步算子：先 `submit` 获取 `task_id`，再 `poll` 轮询直到 `COMPLETED/FAILED`。

## Base / Region

- API Base: `https://operator.las.<region>.volces.com/api/v1`
- Region:
  - `cn-beijing`
  - `cn-shanghai`
- 鉴权：`Authorization: Bearer $LAS_API_KEY`

## Submit 请求体

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_video_resize`（CLI 自动填充） |
| operator_version | string | 是 | 固定为 `v1`（CLI 自动填充） |
| data | VideoResizeReqParams | 是 | **`data.json` 的内容对应此字段**，详情见下 |

### VideoResizeReqParams

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| video_path | string | 是 | 输入视频 TOS 路径或可下载 URL（`tos://bucket/key` 或 `http/https`） |
| output_tos_dir | string | 是 | 输出目录（`tos://bucket/prefix/`） |
| output_file_name | string | 是 | 输出文件名（同名会覆盖） |
| min_width | integer | 是 | 最小宽度（像素） |
| max_width | integer | 是 | 最大宽度（像素） |
| min_height | integer | 是 | 最小高度（像素） |
| max_height | integer | 是 | 最大高度（像素） |
| force_original_aspect_ratio_type | string | 否 | `disable/increase/decrease`，默认 `increase` |
| force_divisible_by | integer | 否 | 像素对齐步长，默认 2 |
| cq | integer | 否 | NVENC 质量参数（0-51，0=自动） |
| rc | string | 否 | NVENC 码率模式（`constqp/vbr/cbr`，默认 `vbr`） |

## Poll 请求体

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_video_resize`（CLI 自动填充） |
| operator_version | string | 是 | 固定为 `v1`（CLI 自动填充） |
| task_id | string | 是 | submit 返回的任务 ID（CLI 自动填充） |

## Poll 响应体（摘要）

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| metadata.task_status | string | `ACCEPTED/RUNNING/COMPLETED/FAILED` |
| data.output_path | string | 输出视频 TOS 路径 |
| data.width | integer | 输出宽度 |
| data.height | integer | 输出高度 |
| data.duration | float | 视频时长 |
