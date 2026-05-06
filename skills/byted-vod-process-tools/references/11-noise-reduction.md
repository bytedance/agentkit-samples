# 音频降噪 `noise_reduction`

智能消除环境噪音、电流杂音、风噪等，提升人声清晰度。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `Vid`（视频ID）或 `DirectUrl`（VOD存储FileName） |
| `audio` | string | ✅ | 音频的 Vid 或 FileName |

> **注意**：`type` 首字母大写（`Vid` / `DirectUrl`）。

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "Success",
  "SpaceName": "my_space",
  "VideoUrls": [
    {"FileId": "xxx", "DirectUrl": "output.m4a", "Url": "https://cdn.example.com/output.m4a"}
  ],
  "AudioUrls": [],
  "Texts": []
}
```

> `audioNoiseReduction` 属于 enhance 类任务，产物在 `VideoUrls`（文件格式为音频，命名沿用 API 字段）。

轮询超时时返回 `error` + `resume_hint`，可用其中的 `command` 重启轮询：

```bash
python <SKILL_DIR>/scripts/poll_media.py 'audioNoiseReduction' '<RunId>' [space_name]
```

## 示例

```bash
# 提交降噪任务并等待结果（一步完成）
python <SKILL_DIR>/scripts/noise_reduction.py \
  '{"type":"Vid","audio":"v0310abc"}'
```
