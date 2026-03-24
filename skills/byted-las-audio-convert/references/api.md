---
title: las_audio_convert API 参考
---

# `las_audio_convert` API 参考

## Base / Region

- Endpoint: `https://operator.las.cn-beijing.volces.com/api/v1/process`
- Method: POST

鉴权：`Authorization: Bearer $LAS_API_KEY`

## 请求体定义

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_audio_convert` |
| operator_version | string | 是 | 固定为 `v1` |
| data | AudioConvertReqParams | 是 | 参数详情见下表 |

### AudioConvertReqParams

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| input_path | string | 是 | 待转换音频文件的 TOS 地址 (tos://bucket/key) |
| output_path | string | 是 | 转换后音频文件的 TOS 地址 (tos://bucket/key) |
| output_format | string | 否 | 转换目标格式。支持 wav, mp3, flac，默认 wav |
| extra_params | List<string> | 否 | 额外 ffmpeg 参数列表，如 `["-ar", "44100"]` |

## 响应体定义

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| metadata | metadata | 请求元信息，包含 status, business_code, request_id 等 |
| data | AudioConvertResponse | 返回数据（可能是 JSON 对象或 JSON 字符串） |

### AudioConvertResponse

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| audios | list<Audio> | 转换结果列表 |

### Audio

| 名称 | 类型 | 描述 |
| :--- | :--- | :--- |
| input_path | string | 输入路径 |
| output_path | string | 输出路径 |
| duration | float | 音频时长 |
| status | string | 转换状态 (success/failed) |

## 业务码

| 业务码 | 含义 |
| :--- | :--- |
| 0 | 正常返回 |
| 1001 | 通用请求端异常 |
| 1002 | 缺失鉴权请求头 |
| 1003 | API Key 无效 |
| 1004 | 指定的 Operator 无效 |
| 1006 | 请求入参格式有误 |
| 2001 | 通用服务端异常 |
