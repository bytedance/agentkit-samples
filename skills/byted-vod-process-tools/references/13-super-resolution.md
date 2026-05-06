# AI 超分辨率 `super_resolution`

AI 智能提升视频分辨率（如 720P → 1080P），同步锐化画面细节。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `Vid` 或 `DirectUrl` |
| `video` | string | ✅ | 视频 Vid 或 FileName |
| `Res` | string | 二选一 | 目标分辨率预设（见下表） |
| `ResLimit` | int | 二选一 | 目标长边/短边最大像素值，范围 [64, 2160] |

> **`Res` 和 `ResLimit` 不能同时指定**，否则返回错误。

### Res 可选值

| 值 | 含义 |
|----|------|
| `240p` | 240P |
| `360p` | 360P |
| `480p` | 480P |
| `540p` | 540P |
| `720p` | 720P（HD） |
| `1080p` | 1080P（Full HD） |
| `2k` | 2K |
| `4k` | 4K |

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

> task_type 为 `videSuperResolution`（注意官方拼写：`vide` 非 `video`）。

轮询超时时返回 `error` + `resume_hint`，可用其中的 `command` 重启轮询：

```bash
python <SKILL_DIR>/scripts/poll_media.py 'videSuperResolution' '<RunId>' [space_name]
```

## 示例

```bash
# 超分至 1080P
python <SKILL_DIR>/scripts/super_resolution.py \
  '{"type":"Vid","video":"v0310abc","Res":"1080p"}'

# 限制长边不超过 1920px
python <SKILL_DIR>/scripts/super_resolution.py \
  '{"type":"Vid","video":"v0310abc","ResLimit":1920}'
```
