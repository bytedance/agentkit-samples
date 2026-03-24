---
title: las_asr_pro API 速查
---

# `las_asr_pro` API 速查

## Base / Region

- Endpoint（文档给出的）：`https://operator.las.cn-beijing.volces.com`
- API Base：`https://operator.las.<region>.volces.com/api/v1`
- 常见 region：`cn-beijing` / `cn-shanghai`

鉴权：`Authorization: Bearer $LAS_API_KEY`

## submit

### 路径

- `POST /api/v1/submit`

### 请求体

顶层字段：

- `operator_id` (string, 必填)：`las_asr_pro`
- `operator_version` (string, 必填)：`v1`
- `data` (SpeechRecognition, 必填)

`data` = SpeechRecognition：

- `user` (UserConfig, 可选)：用户相关配置
- `audio` (Audio, 必填)：音频相关配置
- `resource` (string, 可选)：`bigasr` / `seedasr`（默认 `bigasr`）
- `request` (RequestConfig, 必填)：请求相关配置

UserConfig：

- `uid` (string, 可选)：用户标识

Audio：

- `url` (string, 必填)：音频链接
- `format` (string, 必填)：音频容器格式
- `language` (string, 可选)：不传/为空则自动语种识别；例如 `de`/`de-DE`/`zh` 等
- `codec` (string, 可选)：音频编码格式
- `rate` (int, 可选)：采样率
- `bits` (int, 可选)：采样点位数
- `channel` (int, 可选)：声道数

RequestConfig：

- `model_name` (string, 必填)：模型名称，文档为 `bigmodel`
- `model_version` (string, 可选)：传 `"400"` 使用 400 模型；不传默认 310
- `enable_itn` (bool, 可选，默认 true)：文本规范化
- `enable_punc` (bool, 可选，默认 false)：标点
- `enable_ddc` (bool, 可选，默认 false)：语义顺滑
- `enable_speaker_info` (bool, 可选，默认 false)：说话人信息（10 人以内效果较好）
- `enable_channel_split` (bool, 可选，默认 false)：双声道区分（返回 `channel_id`，1 左 / 2 右）
- `show_utterances` (bool, 可选)：输出停顿/分句/分词信息
- `show_speech_rate` (bool, 可选，默认 false)：分句 additions 携带 `speech_rate`（token/s）
- `show_volume` (bool, 可选，默认 false)：分句 additions 携带 `volume`（dB）
- `enable_lid` (bool, 可选)：启用语种识别（文档：中英文、上海话、闽南语、四川、陕西、粤语）
- `enable_emotion_detection` (bool, 可选，默认 false)：情绪识别（angry/happy/neutral/sad/surprise）
- `enable_gender_detection` (bool, 可选，默认 false)：性别识别（male/female）
- `vad_segment` (bool, 可选，默认 false)：VAD 分句（静音分句）
- `end_window_size` (int, 可选)：300-5000ms，建议 800/1000（用于静音分句窗口）
- `sensitive_words_filter` (string, 可选)：敏感词过滤配置（通常为 JSON 字符串，示例见下）
- `enable_poi_fc` (bool, 可选)：地图领域推荐词辅助识别
- `enable_music_fc` (bool, 可选)：音乐领域推荐词辅助识别
- `enable_denoise` (bool, 可选)：降噪
- `enable_multi_language` (bool, 可选，默认 true)：语种识别和多语种支持
- `corpus` (Corpus, 可选)：语料/干预词

Corpus：

- `context` (string, 可选)：热词直传/上下文等（如果是 JSON，需要自行转义引号）

`sensitive_words_filter` 示例（注意：这是字符串）：

```bash
"{\"system_reserved_filter\":true,\"filter_with_empty\":[\"敏感词\"],\"filter_with_signed\":[\"敏感词\"]}"
```

### 响应体

- `metadata`：请求元信息
  - `task_id`：异步任务 ID
  - `task_status`：任务状态
  - `business_code`：业务码
  - `error_msg`：错误信息
  - `request_id`：请求 ID

## poll

### 路径

- `POST /api/v1/poll`

### 请求体

- `operator_id` (string, 必填)：`las_asr_pro`
- `operator_version` (string, 必填)：`v1`
- `task_id` (string, 必填)

### 响应体

- `metadata`：同 submit
- `data` (AudioResponse)

AudioResponse：

- `audio_info` (AudioInfo)
  - `duration` (long)：音频时长
- `result` (AudioResult)
  - `text` (string)：识别文本
  - `utterances` (list[Utterance])：分句/停顿信息（需开启 `show_utterances`）
  - `additions` (RequestAdditions)：额外信息

RequestAdditions：

- `duration` (string)
- `lid_lang` (string)

Utterance：

- `start_time` (long)
- `end_time` (long)
- `text` (string)
- `confidence` (int)
- `words` (list[Word])
- `additions` (Additions)：如说话人/情绪/性别/音量/语速/声道等

Additions（常见字段）：

- `speaker` / `channel_id`
- `emotion` / `emotion_score` / `emotion_degree` / `emotion_degree_score`
- `gender` / `gender_score`
- `speech_rate` / `volume`

Word：

- `start_time` / `end_time` / `text`
- `confidence` / `blank_duration`

## 任务状态

- `ACCEPTED`：提交成功
- `PENDING`：阻塞中，尚未开始运行
- `RUNNING`：运行中
- `COMPLETED`：完成
- `FAILED`：失败
- `TIMEOUT`：超时

## 错误码

- 400 `Parameter.Invalid`：参数不合法
- 401 `Authorization.Missing`：缺少鉴权
- 401 `ApiKey.InValid`：API Key 不合法
- 429 `Server.Busy`：服务端限流
- 500 `Server.InternalError`：业务异常（如静音音频/空音频/格式不正确/内部错误等）
