# 音视频合成 `compile`

将独立视频轨和音频轨合并为单一文件，可替换或叠加视频原声。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video` | dict | ✅ | 视频信息：`{"type":"vid","source":"v0001"}` |
| `audio` | dict | ✅ | 音频信息：`{"type":"vid","source":"v0002"}` |
| `is_audio_reserve` | bool | 可选 | 是否保留原视频原声，默认 `true` |
| `is_video_audio_sync` | bool | 可选 | 是否对齐音视频时长，默认 `false`（不对齐则以较长流为准） |
| `sync_mode` | string | 可选 | 对齐基准（仅 sync=true 时生效）：`video`（默认）/ `audio` |
| `sync_method` | string | 可选 | 对齐方式（仅 sync=true 时生效）：`trim`（裁剪，默认）/ `speed`（变速） |

### video / audio 子字段

| 字段 | 说明 |
|------|------|
| `type` | `vid` / `directurl` / `http` |
| `source` | 文件标识 |

## 返回值

任务自动轮询至终态，成功时返回：

```json
{
  "Status": "success",
  "OutputJson": {
    "vid": "v0310xxx",
    "url": "https://cdn.example.com/output.mp4"
  }
}
```

## 示例

```bash
# 替换视频背景音（不保留原声）
python <SKILL_DIR>/scripts/compile.py \
  '{"video":{"type":"vid","source":"v0001"},
    "audio":{"type":"vid","source":"v0002"},
    "is_audio_reserve":false}'

# 叠加背景音，并以视频时长为准裁剪音频
python <SKILL_DIR>/scripts/compile.py \
  '{"video":{"type":"vid","source":"v0001"},
    "audio":{"type":"http","source":"https://example.com/bgm.mp3"},
    "is_video_audio_sync":true,"sync_mode":"video","sync_method":"trim"}'
```
