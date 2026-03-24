---
title: las_audio_extract_and_split API 参考
---

# `las_audio_extract_and_split` API 参考

## Base / Region

- Endpoint: `https://operator.las.cn-beijing.volces.com/api/v1/process`
- Method: POST

鉴权：`Authorization: Bearer $LAS_API_KEY`

## 请求体定义

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_audio_extract_and_split` |
| operator_version | string | 是 | 固定为 `v1` |
| data | process_param | 是 | 参数详情见下表 |

### process_param

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| input_path | String | 是 | 输入tos路径。支持格式：`mp4`, `wmv`, `webm`, `mkv`, `m4v`, `flv`, `avi`, `mov` |
| output_path_template | String | 是 | 输出文件路径模版。<br>可用变量：<br>`{index}` 下标<br>`{index1}` 下标+1<br>`{ordinal}` 序数词(1st, etc)<br>`{hours}` 小时数<br>`{duration}` 时长(秒)<br>`{output_file_ext}` 后缀<br>例子：`tos://testbucket/{index}.{output_file_ext}` |
| split_duration | Double | 否 | 每个片段的时长（秒），默认为 30.0 |
| output_format | String | 否 | 输出文件格式，仅支持 "wav", "mp3", "flac"，默认为 "wav" |
| timeout | Integer | 否 | ffmpeg 执行超时时间（秒），默认为 无超时 |
| extra_params | List<String> | 否 | 额外的 ffmpeg 参数列表，例如: `["-ar", "16000", "-ac", "1"]` |

## 响应体定义

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| output_paths | List<String> | 输出的音频文件路径列表 |
| metrics | List<Metric> | 指标列表 |

### Metric

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| name | String | 指标名称。支持 `duration_ms` 音频总毫秒数 |
| value | Integer | 指标值 |

## 错误码

| HttpCode | 错误码 | 说明 |
| :--- | :--- | :--- |
| 401 | Authorization.Missing | 缺少鉴权 |
| 401 | ApiKey.Invalid | API Key 不合法 |
