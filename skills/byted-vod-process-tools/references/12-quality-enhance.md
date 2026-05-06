# 综合画质修复 `quality_enhance`

AI 综合修复视频质量：消除压缩伪影、噪点、划痕，提升整体清晰度与色彩表现。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `Vid`（视频ID）或 `DirectUrl`（VOD存储FileName） |
| `video` | string | ✅ | 视频的 Vid 或 FileName |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "Success",
  "SpaceName": "my_space",
  "VideoUrls": [
    {"FileId": "xxx", "DirectUrl": "output.mp4", "Url": "https://cdn.example.com/output.mp4"}
  ],
  "AudioUrls": [],
  "Texts": []
}
```

轮询超时时返回 `error` + `resume_hint`，可用其中的 `command` 重启轮询：

```bash
python <SKILL_DIR>/scripts/poll_media.py 'enhanceVideo' '<RunId>' [space_name]
```

## 示例

```bash
# 提交画质修复任务并等待结果（一步完成）
python <SKILL_DIR>/scripts/quality_enhance.py \
  '{"type":"Vid","video":"v0310abc"}'
```
