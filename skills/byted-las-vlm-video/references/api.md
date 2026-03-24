---
title: las_vlm_video API 参考
---

# `las_vlm_video` API 参考

## Base / Region

- Endpoint: `https://operator.las.<region>.volces.com/api/v1/process`
- Method: POST
- Region:
  - `cn-beijing` → `operator.las.cn-beijing.volces.com`
  - `cn-shanghai` → `operator.las.cn-shanghai.volces.com`
- 鉴权：`Authorization: Bearer $LAS_API_KEY`

## 请求体定义

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_vlm_video` |
| operator_version | string | 是 | 固定为 `v1` |
| data | vlm_info | 是 | 算子参数 |

### vlm_info（常用字段）

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| messages | list | 是 | 对话消息列表。常见为单条 user 消息，包含 `video_url` + `text` |
| model_name | string | 否 | 缺省 `doubao-seed-1.6-vision` |
| min_resolution_height | integer | 否 | 视频最低垂直像素，默认 360 |
| compress_fps | float | 否 | 压缩抽帧后的帧率，默认 5.0 |
| max_tokens | integer | 否 | 输出最大长度（token），不同模型上限不同 |
| max_completion_tokens | integer | 否 | 超长输出控制字段（与 max_tokens 互斥） |
| temperature | float | 否 | 采样温度（0~2） |
| top_p | float | 否 | 核采样概率阈值（0~1） |
| stop | list<string> | 否 | 停止词 |

### messages 推荐结构（示例）

```json
[
  {
    "role": "user",
    "content": [
      {"type": "video_url", "video_url": {"url": "https://example.com/video.mp4"}},
      {"type": "text", "text": "请总结视频内容，并列出关键事件。"}
    ]
  }
]
```

## 响应体定义（摘要）

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| metadata | object | `task_status`, `business_code`, `error_msg`, `request_id` |
| data | object | `vlm_result`（模型对话原生返回）与 `compress_result`（压缩结果与耗时） |

`vlm_result` 的结构参考「对话(Chat) API」的响应字段。常见场景可直接使用：

- `data.vlm_result.choices[0].message.content` 作为主要文本输出
