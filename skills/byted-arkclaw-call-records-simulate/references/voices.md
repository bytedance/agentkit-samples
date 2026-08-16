# edge-tts 常用中文语音模型

> 完整列表可通过 `edge-tts --list-voices | grep zh-` 获取。以下为通话记录场景最常用的几个，按"主叫 / 被叫"搭配推荐。

## 普通话（zh-CN）

| voice | 性别 | 音色特征 | 推荐角色 |
|-------|------|----------|----------|
| `zh-CN-XiaoxiaoNeural` | 女 | 标准、亲和，偏客服/猎头 | 主叫（销售 / 猎头 / 客服） |
| `zh-CN-XiaoyiNeural`   | 女 | 温柔、偏年轻 | 被叫（候选人 / 客户） |
| `zh-CN-YunxiNeural`    | 男 | 标准、沉稳 | 主叫 / 被叫（商务） |
| `zh-CN-YunyangNeural`  | 男 | 浑厚、偏新闻播报 | 主叫（外呼通知 / 政务） |
| `zh-CN-YunjianNeural`  | 男 | 自然、略松弛 | 被叫（技术候选人 / 客户） |
| `zh-CN-XiaochenNeural` | 女 | 清亮、利落 | 主叫（信贷 / 催收） |

## 其他中文

| voice | 说明 |
|-------|------|
| `zh-HK-HiuGaaiNeural` / `zh-HK-WanLungNeural` | 粤语男女声 |
| `zh-TW-HsiaoChenNeural` / `zh-TW-YunJheNeural` | 台湾国语男女声 |

## 搭配建议

- **男女组合更利于 ASR 说话人分离**：主叫 / 被叫各取一方性别。
- **同性别搭配**：若必须同性别，至少在 voice 上区分（例如 `XiaoxiaoNeural` + `XiaoyiNeural`），避免让下游 speaker diarization 误判为同一人。
- **严肃场景**：使用 `YunyangNeural` / `YunxiNeural` 主叫，语感更权威。
- **轻松场景**：使用 `XiaoyiNeural` / `YunjianNeural`，语感更日常。
