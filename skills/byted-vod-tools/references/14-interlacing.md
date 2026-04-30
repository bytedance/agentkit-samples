# 智能补帧 `interlacing`

用运动补偿算法将低帧率视频（如 24fps/30fps）插帧至高帧率（如 60fps），使运动场景更流畅。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `Vid` 或 `DirectUrl` |
| `video` | string | ✅ | 视频 Vid 或 FileName |
| `Fps` | float | ✅ | 目标帧率（fps），范围 **(0, 120]** |

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
python <SKILL_DIR>/scripts/poll_media.py 'videoInterlacing' '<RunId>' [space_name]
```

## 示例

```bash
# 将 30fps 视频补帧至 60fps
python <SKILL_DIR>/scripts/interlacing.py \
  '{"type":"Vid","video":"v0310abc","Fps":60}'
```
