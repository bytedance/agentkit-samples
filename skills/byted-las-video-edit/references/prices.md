# 计费信息


- 视频智能剪辑 simple 模式：1.5 元/分钟
- 视频智能剪辑 detail 模式：2 元/分钟

## 预估方式（元）

- 用 `lasutil media-duration <video_url>` 获取 `duration_seconds`
- `duration_minutes = duration_seconds / 60`
- `estimated_price_yuan = duration_minutes * rate_yuan_per_minute`

`rate_yuan_per_minute` 取决于请求体里的 `mode`（simple/detail）。
