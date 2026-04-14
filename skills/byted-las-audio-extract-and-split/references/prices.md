# 计费信息

- 智能音频切分：0.003 元/分钟

## 预估方式（元）

- 用 `lasutil media-duration <audio_url>` 获取 `duration_seconds`
- `duration_minutes = duration_seconds / 60`
- `estimated_price_yuan = duration_minutes * 0.003`
