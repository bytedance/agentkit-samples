# 人声分离 `voice_separation`

将视频或音频中的人声与背景音乐精确分离，输出两个独立音频文件。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `Vid`（视频ID）或 `DirectUrl`（VOD存储FileName） |
| `video` | string | ✅ | 视频/音频的 Vid 或 FileName |

> **注意**：`type` 首字母大写（`Vid` / `DirectUrl`），与编辑类工具不同。

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "Success",
  "SpaceName": "my_space",
  "AudioUrls": [
    {"DirectUrl": "voice.m4a",  "Vid": "", "Type": "voice",      "Url": "https://cdn.example.com/voice.m4a"},
    {"DirectUrl": "bg.m4a",     "Vid": "", "Type": "background", "Url": "https://cdn.example.com/bg.m4a"}
  ],
  "VideoUrls": [],
  "Texts": []
}
```

| AudioUrls[].Type | 含义 |
|------------------|------|
| `voice` | 提取的人声音频 |
| `background` | 提取的背景音乐 |

轮询超时时返回 `error` + `resume_hint`，可用其中的 `command` 重启轮询：

```bash
python <SKILL_DIR>/scripts/poll_media.py 'voiceSeparation' '<RunId>' [space_name]
```

## 示例

```bash
# 提交任务并等待结果（一步完成）
python <SKILL_DIR>/scripts/voice_separation.py \
  '{"type":"Vid","video":"v0310abc"}'
```
