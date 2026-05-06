# 硬字幕擦除 `subtitle_removal`

智能检测并无缝擦除视频画面中已有的硬字幕，保留原始背景。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 输入类型：`Vid` 或 `DirectUrl` |
| `video` | string | ✅ | 当 type 为 `Vid` 时为视频 ID；当 type 为 `DirectUrl` 时为 FileName |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "Success",
  "VideoUrls": [
    {
      "FileId": "xxx",
      "DirectUrl": "path/to/output.mp4",
      "Url": "https://cdn.example.com/output.mp4"
    }
  ]
}
```

## 示例

```bash
# 擦除视频中的硬字幕
python <SKILL_DIR>/scripts/subtitle_removal.py \
  '{"type":"Vid","video":"v0310abc"}'

# DirectUrl 模式
python <SKILL_DIR>/scripts/subtitle_removal.py \
  '{"type":"DirectUrl","video":"path/to/file.mp4"}'
```
