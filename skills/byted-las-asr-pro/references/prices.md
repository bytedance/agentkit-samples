# 计费信息

<br />
- 语音转文字（豆包语音）增强版 2.0：1.6 元/小时
- 语音转文字（豆包语音）增强版 1.0：4.6 元/小时

当前 `las_asr_pro` 的具体计费档位取决于服务端配置与请求参数（例如模型版本）。如果无法确定，应在预估价格阶段追问用户或提示“计费档位待确认”。

## 预估方式（元）

- 用 `lasutil media-duration <audio_url>` 获取 `duration_seconds`
- `duration_hours = duration_seconds / 3600`
- `estimated_price_yuan = duration_hours * rate_yuan_per_hour`

