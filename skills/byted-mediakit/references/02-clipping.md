# 视频/音频裁剪 `clipping`

按时间段裁剪视频或音频片段。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `video` 或 `audio` |
| `source` | string | ✅ | 源文件，格式：`vid://xxx` / `directurl://xxx` / 公网 URL |
| `start_time` | float | ✅ | 裁剪开始时间（秒），支持 2 位小数，默认 0 |
| `end_time` | float | ✅ | 裁剪结束时间（秒），必须 > start_time |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "success",
  "OutputJson": {
    "vid": "v0310xxx",
    "url": "https://cdn.example.com/output.mp4",
    "duration": 20.0
  }
}
```

## 示例

```bash
# 裁剪视频 10s~30s 片段
python <SKILL_DIR>/scripts/clipping.py \
  '{"type":"video","source":"vid://v0001","start_time":10,"end_time":30}'

# 裁剪音频
python <SKILL_DIR>/scripts/clipping.py \
  '{"type":"audio","source":"vid://v0002","start_time":5.5,"end_time":60}'
```
